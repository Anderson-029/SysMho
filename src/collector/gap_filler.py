"""
SysMho — Relleno Automático de Vacíos de Datos (Gap Filler).

Al arrancar, detecta qué velas faltan en market_data para cada
símbolo × timeframe y las descarga de Binance antes de que los
WebSockets y el motor de señales entren en línea.

Garantiza que el modelo siempre entrene y prediga sobre datos
continuos, sin huecos por períodos en que SysMho estuvo apagado.

Flujo:
  1. detect_gaps()   → encuentra el último timestamp por símbolo×TF
  2. fill_all_gaps() → descarga e inserta las velas faltantes
  3. Llamado desde main.py en start() antes de lanzar WebSockets
"""

import asyncio
import os
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import ccxt.async_support as ccxt

from src.database.repository import DatabaseRepository
from src.runtime_config import set_sync_status

# Timeframes que SysMho necesita completos
TIMEFRAMES = ['5m', '1h', '4h']

# Duración de cada vela en segundos (para calcular cuántas faltan)
TF_SECONDS = {'5m': 300, '1h': 3600, '4h': 14400}

# Máx velas por request (límite de Binance)
BATCH_LIMIT = 1000

# Pausa entre requests para respetar rate limit (ms → s)
RATE_LIMIT_SLEEP = 0.25

# Log al brain.log
_BRAIN_LOG = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'sysmho_brain.log'
)


def _log(msg: str) -> None:
    ts = time.strftime('%H:%M:%S')
    line = f"[{ts}] {msg}"
    try:
        with open(_BRAIN_LOG, 'a', encoding='utf-8') as f:
            f.write(line + '\n')
    except Exception:
        pass
    print(line)


class GapFiller:
    """
    Detecta y rellena vacíos de datos históricos al arrancar SysMho.
    """

    def __init__(self, db: DatabaseRepository) -> None:
        self.db = db
        # Exchange sin autenticación — OHLCV histórico es endpoint público
        self.exchange = ccxt.binance({
            'enableRateLimit': True,
            'options': {'defaultType': 'future'},
        })

    async def detect_gaps(
        self, symbols: List[str]
    ) -> Dict[str, Dict[str, Optional[int]]]:
        """
        Consulta la BD y devuelve el timestamp (ms) de la última vela
        registrada por símbolo × timeframe.

        Returns:
            {symbol: {timeframe: last_ts_ms | None}}
            None significa que no hay ninguna vela → necesita descarga completa.
        """
        gaps = {}
        query = '''
            SELECT symbol, timeframe, MAX(open_time) AS last_candle
            FROM market_data
            WHERE symbol = ANY($1::text[])
              AND timeframe = ANY($2::text[])
            GROUP BY symbol, timeframe
        '''
        async with self.db.pool.acquire() as conn:
            rows = await conn.fetch(query, symbols, TIMEFRAMES)

        # Indexar resultados
        known: Dict[Tuple[str, str], int] = {}
        for row in rows:
            sym = row['symbol']
            tf = row['timeframe']
            last = row['last_candle']
            if last:
                known[(sym, tf)] = int(last.timestamp() * 1000)

        for sym in symbols:
            gaps[sym] = {}
            for tf in TIMEFRAMES:
                gaps[sym][tf] = known.get((sym, tf))  # None si no existe

        return gaps

    async def fill_all_gaps(self, symbols: List[str]) -> None:
        """
        Punto de entrada principal. Detecta todos los vacíos y los rellena.
        Loguea progreso en telemetría.
        """
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        gaps = await self.detect_gaps(symbols)

        # Calcular trabajo total
        tasks_needed = []
        for sym in symbols:
            for tf in TIMEFRAMES:
                last_ts = gaps[sym][tf]
                tf_secs = TF_SECONDS[tf]
                if last_ts is None:
                    # Sin datos — se encarga el backfill inicial, no este módulo
                    continue
                gap_secs = (now_ms - last_ts) / 1000
                missing = int(gap_secs / tf_secs)
                if missing >= 2:  # al menos 2 velas de diferencia = vacío real
                    tasks_needed.append((sym, tf, last_ts, missing))

        if not tasks_needed:
            _log("✅ [GAP FILLER] Datos al día — sin vacíos detectados.")
            set_sync_status('idle')
            return

        total_candles = sum(t[3] for t in tasks_needed)
        _log(f"🔍 [GAP FILLER] ══════════════════════════════════════")
        _log(f"🔍 [GAP FILLER] {len(tasks_needed)} vacío(s) detectado(s) | {total_candles} velas totales")
        for sym, tf, last_ts, missing in tasks_needed:
            last_dt = datetime.fromtimestamp(last_ts / 1000, tz=timezone.utc)
            _log(f"🔍 [GAP FILLER] {sym} {tf} — desde {last_dt.strftime('%Y-%m-%d %H:%M')} UTC → {missing} velas")
        _log(f"🔍 [GAP FILLER] ══════════════════════════════════════")

        # Rellenar cada vacío
        set_sync_status('syncing', f'{len(tasks_needed)} vacío(s) — {total_candles} velas')
        filled_total = 0
        for i, (sym, tf, last_ts, missing) in enumerate(tasks_needed, 1):
            set_sync_status('syncing', f'{sym} {tf} ({i}/{len(tasks_needed)})')
            filled = await self._fill_gap(sym, tf, last_ts + 1, now_ms)
            filled_total += filled

        set_sync_status('idle')
        _log(f"✅ [GAP FILLER] ══════════════════════════════════════")
        _log(f"✅ [GAP FILLER] Sincronización completa — {filled_total} velas insertadas")
        _log(f"✅ [GAP FILLER] Datos al día. Motor listo para operar.")
        _log(f"✅ [GAP FILLER] ══════════════════════════════════════")

        await self.exchange.close()

    async def _fill_gap(
        self, symbol: str, timeframe: str, since_ms: int, until_ms: int
    ) -> int:
        """
        Descarga e inserta en lotes todas las velas entre since_ms y until_ms.

        Returns: número de velas insertadas.
        """
        inserted = 0
        current_since = since_ms

        while current_since < until_ms:
            try:
                ohlcv = await self.exchange.fetch_ohlcv(
                    symbol, timeframe, current_since, BATCH_LIMIT
                )
            except ccxt.NetworkError as e:
                _log(f"⚠️ [GAP FILLER] Red — {symbol} {timeframe}: {e}. Reintentando...")
                await asyncio.sleep(5)
                continue
            except Exception as e:
                _log(f"❌ [GAP FILLER] Error {symbol} {timeframe}: {e}")
                break

            if not ohlcv:
                break

            records = []
            for row in ohlcv:
                ts_ms = row[0]
                if ts_ms > until_ms:
                    break
                open_time = datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc)
                records.append((
                    symbol, timeframe, open_time,
                    float(row[1]), float(row[2]),
                    float(row[3]), float(row[4]), float(row[5]),
                ))

            if records:
                await self.db.insert_market_data_batch(records)
                inserted += len(records)

            # Avanzar al siguiente lote
            last_ts = ohlcv[-1][0]
            if last_ts >= until_ms or len(ohlcv) < BATCH_LIMIT:
                break
            current_since = last_ts + 1

            await asyncio.sleep(RATE_LIMIT_SLEEP)

        if inserted:
            _log(f"📥 [GAP FILLER] {symbol} {timeframe} — {inserted} velas rellenadas")

        return inserted
