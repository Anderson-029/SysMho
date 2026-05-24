"""
SysMho — Repositorio de Base de Datos.

Módulo de persistencia asíncrona usando asyncpg.
Maneja la conexión a la base de datos PostgreSQL, la inserción
masiva y viva de velas OHLCV, y la sincronización del portafolio.
"""

from datetime import datetime

import asyncpg
from typing import List, Tuple, Optional, Any

from config.settings import DATABASE_URL


def _compute_atr(records: List[Tuple], period: int = 14) -> List[Optional[float]]:
    """
    Calcula ATR-14 (SMA del True Range) para un lote de velas ordenadas.

    Asume que records están ordenados por open_time ASC.
    Índices esperados: (symbol, timeframe, open_time, open, high, low, close, volume)
    """
    trs = []
    prev_close = None
    for rec in records:
        high  = float(rec[4])
        low   = float(rec[5])
        close = float(rec[6])
        if prev_close is None:
            tr = high - low
        else:
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        trs.append(tr)
        prev_close = close

    atrs: List[Optional[float]] = []
    for i in range(len(trs)):
        if i < period - 1:
            atrs.append(None)
        else:
            atrs.append(sum(trs[i - period + 1: i + 1]) / period)
    return atrs


class DatabaseRepository:
    """Clase principal para la interacción asíncrona con PostgreSQL."""

    def __init__(self) -> None:
        """Inicializa el repositorio sin conexión activa."""
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self) -> None:
        """Crea el pool de conexiones asíncronas si no existe."""
        if not self.pool:
            self.pool = await asyncpg.create_pool(
                DATABASE_URL,
                min_size=5,
                max_size=50
            )

    async def close(self) -> None:
        """Cierra el pool de conexiones de manera ordenada."""
        if self.pool:
            await self.pool.close()
            self.pool = None

    async def insert_market_data_batch(self, data_list: List[Tuple]) -> None:
        """
        Inserta de forma masiva (Bulk Insert) las velas OHLCV en market_data.
        Calcula e incluye atr_14 para cada vela del lote.

        Args:
            data_list: Lista de tuplas con el formato esperado:
                (symbol, timeframe, open_time, open, high, low, close, volume)
        """
        if not data_list:
            return

        # Ordenar por open_time para el cálculo correcto de ATR
        sorted_data = sorted(data_list, key=lambda r: r[2])
        atrs = _compute_atr(sorted_data)

        # Construir 9-tuplas incluyendo atr_14
        records_with_atr = [(*rec, atr) for rec, atr in zip(sorted_data, atrs)]

        query = '''
            INSERT INTO market_data
                (symbol, timeframe, open_time, open, high, low, close, volume, atr_14)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            ON CONFLICT (symbol, timeframe, open_time) DO UPDATE SET
                high   = EXCLUDED.high,
                low    = EXCLUDED.low,
                close  = EXCLUDED.close,
                volume = EXCLUDED.volume,
                atr_14 = COALESCE(EXCLUDED.atr_14, market_data.atr_14);
        '''
        async with self.pool.acquire() as conn:
            await conn.executemany(query, records_with_atr)

    async def backfill_atr_14_all(self) -> None:
        """
        Recalcula atr_14 para todas las filas de market_data por (symbol, timeframe).

        Útil cuando hay datos cargados sin ATR (seeds antiguos o inserts manuales).
        El colector ya calcula ATR en insert_market_data_batch; esto alinea histórico.
        """
        if not self.pool:
            return
        async with self.pool.acquire() as conn:
            pairs = await conn.fetch(
                "SELECT DISTINCT symbol, timeframe FROM market_data"
            )
            for p in pairs:
                symbol, tf = p["symbol"], p["timeframe"]
                rows = await conn.fetch(
                    """
                    SELECT open_time, open, high, low, close, volume
                    FROM market_data
                    WHERE symbol = $1 AND timeframe = $2
                    ORDER BY open_time ASC
                    """,
                    symbol,
                    tf,
                )
                if len(rows) < 14:
                    continue
                tuples: List[Tuple] = [
                    (
                        symbol,
                        tf,
                        r["open_time"],
                        float(r["open"]),
                        float(r["high"]),
                        float(r["low"]),
                        float(r["close"]),
                        float(r["volume"]),
                    )
                    for r in rows
                ]
                atrs = _compute_atr(tuples)
                for rec, atr in zip(tuples, atrs):
                    if atr is not None:
                        await conn.execute(
                            """
                            UPDATE market_data
                            SET atr_14 = $1
                            WHERE symbol = $2 AND timeframe = $3 AND open_time = $4
                            """,
                            atr,
                            symbol,
                            tf,
                            rec[2],
                        )

    async def get_market_data_count(
        self, symbol: str, timeframe: str
    ) -> int:
        """
        Obtiene la cantidad total de velas históricas de un símbolo.

        Args:
            symbol: El par del criptoactivo (ej. 'BTC/USDT').
            timeframe: La temporalidad (ej. '5m').

        Returns:
            int: Número de registros almacenados.
        """
        query = '''
            SELECT COUNT(*) 
            FROM market_data 
            WHERE symbol = $1 AND timeframe = $2;
        '''
        async with self.pool.acquire() as conn:
            return await conn.fetchval(query, symbol, timeframe)

    async def upsert_market_data(self, record: Tuple) -> None:
        """
        Inserta o actualiza una sola vela viva recibida por WebSocket.
        Calcula y actualiza atr_14 usando las últimas 14 velas en BD.

        Args:
            record: Tupla con:
                (symbol, timeframe, open_time, open, high, low, close, volume)
        """
        symbol, timeframe, open_time = record[0], record[1], record[2]

        upsert_query = '''
            INSERT INTO market_data
                (symbol, timeframe, open_time, open, high, low, close, volume)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT (symbol, timeframe, open_time)
            DO UPDATE SET
                high   = EXCLUDED.high,
                low    = EXCLUDED.low,
                close  = EXCLUDED.close,
                volume = EXCLUDED.volume;
        '''
        atr_query = '''
            SELECT high, low, close FROM market_data
            WHERE symbol = $1 AND timeframe = $2
            ORDER BY open_time DESC LIMIT 15
        '''
        update_atr_query = '''
            UPDATE market_data SET atr_14 = $1
            WHERE symbol = $2 AND timeframe = $3 AND open_time = $4
        '''
        async with self.pool.acquire() as conn:
            await conn.execute(upsert_query, *record)

            rows = await conn.fetch(atr_query, symbol, timeframe)
            if len(rows) >= 14:
                # Más reciente último para cálculo correcto
                candles = list(reversed(rows))
                # Construir tuplas mínimas compatibles con _compute_atr
                # índices: [4]=high [5]=low [6]=close
                fake_recs = [
                    (None, None, None, None,
                     float(r['high']), float(r['low']), float(r['close']), None)
                    for r in candles
                ]
                atrs = _compute_atr(fake_recs)
                last_atr = atrs[-1]
                if last_atr is not None:
                    await conn.execute(
                        update_atr_query, last_atr, symbol, timeframe, open_time
                    )

    async def sync_portfolio_on_trade(
        self, amount: float, action: str, pnl: float = 0.0
    ) -> None:
        """
        Gestiona el flujo de caja atómico del portafolio.

        Args:
            amount: Monto en USDT involucrado en la transacción.
            action: 'OPEN' (Bloquea saldo) o 'CLOSE' (Libera y ajusta PNL).
            pnl: Ganancia o pérdida generada (solo usado en 'CLOSE').
        """
        if action == 'OPEN':
            query = '''
                UPDATE portfolio 
                SET available_balance = available_balance - $1,
                    in_positions = in_positions + $1
                WHERE id = (SELECT id FROM portfolio ORDER BY recorded_at DESC LIMIT 1);
            '''
            async with self.pool.acquire() as conn:
                await conn.execute(query, amount)

        elif action == 'CLOSE':
            query = '''
                UPDATE portfolio 
                SET available_balance = available_balance + $1 + $2,
                    in_positions = in_positions - $1,
                    total_balance = total_balance + $2,
                    total_pnl = total_pnl + $2
                WHERE id = (SELECT id FROM portfolio ORDER BY recorded_at DESC LIMIT 1);
            '''
            async with self.pool.acquire() as conn:
                await conn.execute(query, amount, pnl)

    async def sync_wallet_from_exchange(
        self, available_balance: float, total_balance: float, in_positions: float = 0.0
    ) -> None:
        """
        Sobrescribe el portfolio con valores reales obtenidos directamente de Binance.

        A diferencia de sync_portfolio_on_trade (incremental), esta función reemplaza
        los valores absolutos. Usada en startup_reconciliation y correcciones manuales.

        Args:
            available_balance: Balance disponible real desde Binance (availableBalance).
            total_balance: Balance total real desde Binance (totalMarginBalance).
            in_positions: Suma de invested_usdt de posiciones locales abiertas.
        """
        async with self.pool.acquire() as conn:
            await conn.execute(
                """UPDATE portfolio SET
                   available_balance = $1,
                   total_balance = $2,
                   in_positions = $3,
                   recorded_at = NOW()
                   WHERE id = (SELECT id FROM portfolio ORDER BY recorded_at DESC LIMIT 1)
                """,
                available_balance, total_balance, in_positions
            )

    async def upsert_sentiment(
        self, symbol: str, funding_rate: float, open_interest: float
    ) -> None:
        """
        Inserta o actualiza las métricas institucionales de un símbolo.
        """
        query = '''
            INSERT INTO sentiment_data (symbol, funding_rate, open_interest, updated_at)
            VALUES ($1, $2, $3, NOW())
            ON CONFLICT (symbol) DO UPDATE SET 
                funding_rate = EXCLUDED.funding_rate,
                open_interest = EXCLUDED.open_interest,
                updated_at = NOW();
        '''
        async with self.pool.acquire() as conn:
            await conn.execute(query, symbol, funding_rate, open_interest)

    async def upsert_liquidity_radar(self, symbol: str, obi_20: float) -> None:
        """
        Inserta o actualiza el Order Book Imbalance (Liquidity Radar).
        """
        query = '''
            INSERT INTO sentiment_data (symbol, obi_20, updated_at)
            VALUES ($1, $2, NOW())
            ON CONFLICT (symbol) DO UPDATE SET 
                obi_20 = EXCLUDED.obi_20,
                updated_at = NOW();
        '''
        async with self.pool.acquire() as conn:
            await conn.execute(query, symbol, obi_20)

    async def get_sentiment(self, symbol: str) -> Optional[dict]:
        """
        Obtiene el último sentimiento registrado para el activo.

        Returns:
            Dict con 'funding_rate', 'open_interest' y 'obi_20' o None si no existe.
        """
        query = '''
            SELECT funding_rate, open_interest, obi_20
            FROM sentiment_data
            WHERE symbol = $1;
        '''
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, symbol)
            
        if row:
            return {
                'funding_rate': float(row['funding_rate']) if row['funding_rate'] is not None else 0.0,
                'open_interest': float(row['open_interest']) if row['open_interest'] is not None else 0.0,
                'obi_20': float(row['obi_20']) if row['obi_20'] is not None else 0.0
            }
        return None

    async def log_autonomous_decision(
        self,
        pending_id: int,
        symbol: str,
        decision: str,
        meta_score: float,
        confidence: float,
        direction: str,
        reasons: list,
        cb_active: bool = False,
        cb_reason: str = '',
    ) -> None:
        """
        Registra una decisión autónoma del MetaEvaluador en la BD.

        Args:
            pending_id: ID de la señal en pending_approvals.
            symbol: Par del activo.
            decision: 'APPROVED' | 'REJECTED'.
            meta_score: Score compuesto del MetaEvaluador [0..1].
            confidence: Confianza del modelo XGBoost.
            direction: 'LONG' | 'SHORT'.
            reasons: Lista de razones textuales.
            cb_active: True si el CircuitBreaker fue la causa.
            cb_reason: Descripción del trigger del CircuitBreaker.
        """
        query = '''
            INSERT INTO autonomous_decisions
                (pending_id, symbol, decision, meta_score, confidence,
                 direction, reasons, cb_active, cb_reason)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        '''
        async with self.pool.acquire() as conn:
            await conn.execute(
                query,
                pending_id, symbol, decision,
                round(meta_score, 4), round(confidence, 4),
                direction, reasons,
                cb_active, cb_reason or None,
            )

    async def get_autonomous_decisions(self, limit: int = 50) -> list:
        """Obtiene las últimas decisiones autónomas para el dashboard,
        incluyendo el resultado real del trade si ya cerró."""
        query = '''
            SELECT
                ad.id, ad.pending_id, ad.symbol, ad.decision, ad.meta_score,
                ad.confidence, ad.direction, ad.reasons,
                ad.cb_active, ad.cb_reason, ad.created_at,
                (
                    SELECT t.pnl
                    FROM trades t
                    WHERE t.symbol = ad.symbol
                      AND t.status = 'CLOSED'
                      AND t.executed_at > ad.created_at
                    ORDER BY t.executed_at ASC
                    LIMIT 1
                ) AS trade_pnl
            FROM autonomous_decisions ad
            ORDER BY ad.created_at DESC
            LIMIT $1
        '''
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, limit)
        return [dict(r) for r in rows]

    async def get_daily_stats(self) -> dict:
        """
        Estadísticas del día actual para el CircuitBreaker.

        Si existe un cb_reset_at en runtime_state.json, solo cuenta
        trades posteriores a ese timestamp (reset manual de contadores).

        Returns:
            {trades_today, daily_pnl_usdt, consecutive_losses, recent_trades}
        """
        from datetime import date, timedelta, timezone
        from src.runtime_config import get_cb_reset_at
        cb_reset_at = get_cb_reset_at()

        # Límite temporal: el más reciente entre medianoche y el último reset manual.
        # Calculado en Python para evitar interpolación de strings en SQL.
        today_start = datetime.combine(
            date.today(), datetime.min.time()
        ).replace(tzinfo=timezone.utc)
        if cb_reset_at:
            try:
                cb_dt = datetime.fromisoformat(cb_reset_at)
                effective_start = max(today_start, cb_dt)
            except (ValueError, TypeError):
                effective_start = today_start
        else:
            effective_start = today_start

        week_day = date.today() - timedelta(days=date.today().weekday())
        week_start = datetime.combine(week_day, datetime.min.time()).replace(tzinfo=timezone.utc)
        weekly_start = max(week_start, effective_start)

        query_today = '''
            SELECT COUNT(*) AS trades_today,
                   COALESCE(SUM(pnl), 0) AS daily_pnl
            FROM trades
            WHERE status = 'CLOSED'
              AND executed_at >= $1
        '''
        query_recent = '''
            SELECT id, symbol, side, pnl, executed_at
            FROM trades
            WHERE status = 'CLOSED'
              AND executed_at >= $1
            ORDER BY executed_at DESC
            LIMIT 20
        '''
        query_weekly = '''
            SELECT COALESCE(SUM(pnl), 0) AS weekly_pnl
            FROM trades
            WHERE status = 'CLOSED'
              AND executed_at >= $1
        '''
        query_portfolio = '''
            SELECT total_balance
            FROM portfolio
            ORDER BY recorded_at DESC
            LIMIT 1
        '''
        async with self.pool.acquire() as conn:
            today = await conn.fetchrow(query_today, effective_start)
            recent_rows = await conn.fetch(query_recent, effective_start)
            weekly = await conn.fetchrow(query_weekly, weekly_start)
            portfolio = await conn.fetchrow(query_portfolio)

        total_bal = float(portfolio['total_balance']) if portfolio else 1000.0
        daily_pnl = float(today['daily_pnl']) if today else 0.0
        weekly_pnl = float(weekly['weekly_pnl']) if weekly else 0.0

        # Normalizar campos para que sean compatibles con CircuitBreaker y SelfLearner
        recent = []
        for r in recent_rows:
            row = dict(r)
            row['pnl_usdt'] = float(row.get('pnl', 0) or 0)
            recent.append(row)

        # Racha de pérdidas consecutivas (más reciente primero)
        streak = 0
        for t in recent:
            if float(t.get('pnl_usdt', 0)) < 0:
                streak += 1
            else:
                break

        return {
            'trades_today': int(today['trades_today']) if today else 0,
            'daily_pnl_usdt': daily_pnl,
            'daily_pnl_pct': daily_pnl / total_bal if total_bal > 0 else 0.0,
            'weekly_pnl_pct': weekly_pnl / total_bal if total_bal > 0 else 0.0,
            'consecutive_losses': streak,
            'recent_trades': recent,
            'total_balance': total_bal,
        }

    async def save_gemini_context(self, report: dict) -> None:
        """Guarda el ContextReport de Gemini en BD."""
        import json as _json
        query = '''
            INSERT INTO gemini_market_context (
                sentiment_score, whale_pressure, macro_bias,
                news_risk_level, optimal_hour, llm_veto,
                significant_changes, sources_checked,
                full_report, gemini_reasoning,
                was_reinvestigated, reuse_count
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
        '''
        async with self.pool.acquire() as conn:
            await conn.execute(
                query,
                report.get('sentiment_score', 0.0),
                report.get('whale_pressure', 0),
                report.get('macro_bias', 0),
                report.get('news_risk_level', 0),
                report.get('optimal_hour', True),
                report.get('llm_veto', False),
                _json.dumps(report.get('significant_changes', {})),
                report.get('sources_checked', []),
                _json.dumps(report.get('full_report', {})),
                report.get('gemini_reasoning', ''),
                report.get('was_reinvestigated', True),
                report.get('reuse_count', 0),
            )

    async def get_latest_gemini_context(self) -> Optional[dict]:
        """Obtiene el reporte más reciente de Gemini."""
        import json as _json
        import time as _time
        query = '''
            SELECT sentiment_score, whale_pressure, macro_bias,
                   news_risk_level, optimal_hour, llm_veto,
                   significant_changes, sources_checked,
                   full_report, gemini_reasoning,
                   was_reinvestigated, reuse_count,
                   created_at
            FROM gemini_market_context
            ORDER BY created_at DESC
            LIMIT 1
        '''
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query)
        if not row:
            return None
        result = dict(row)
        result['significant_changes'] = _json.loads(result.get('significant_changes') or '{}')
        result['full_report'] = _json.loads(result.get('full_report') or '{}')
        result['sources_checked'] = list(result.get('sources_checked') or [])
        result['sentiment_score'] = float(result.get('sentiment_score') or 0.0)
        result['_timestamp'] = result['created_at'].timestamp() if result.get('created_at') else _time.time()
        return result
