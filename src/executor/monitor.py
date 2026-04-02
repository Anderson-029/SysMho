"""
SysMho — Monitor de Posiciones.

Vigila constantemente las operaciones abiertas en la base de datos,
calcula el PnL no realizado (ROE) en tiempo real, y cierra operaciones
si tocan el Take Profit, el Stop Loss, o si el Escudo de Capital
detecta un riesgo inminente de liquidación.
"""

import asyncio
import os
import time
from typing import Dict, Any

from src.database.repository import DatabaseRepository
from src.constants import BINANCE_FUTURES_TAKER_FEE

_BRAIN_LOG = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "sysmho_brain.log"
)


def _log(msg: str) -> None:
    """Escribe evento crítico en el log neuronal visible en el dashboard."""
    line = f"[{time.strftime('%H:%M:%S')}] [MONITOR] {msg}\n"
    try:
        with open(_BRAIN_LOG, "a", encoding="utf-8") as f:
            f.write(line)
            f.flush()
    except Exception:
        pass
    print(line.rstrip())


class PositionMonitor:
    """Vigilante en tiempo real de las operaciones abiertas."""

    # Frecuencia de vigilancia en segundos (Overclocking v10.1)
    MONITOR_INTERVAL_SECONDS = 1
    # Margen de seguridad antes de liquidación forzada (90%)
    CAPITAL_SHIELD_THRESHOLD = 0.90

    def __init__(self, db: DatabaseRepository, trader: Any = None) -> None:
        """Inicializa el monitor requiriendo conexión a la BD y al Trader."""
        self.db = db
        self.trader = trader
        self.is_running: bool = False

    async def start_monitoring(self) -> None:
        """Inicia el ciclo de vigilancia infinito."""
        self.is_running = True
        print("🛡️ [MONITOR] Iniciando vigilancia de posiciones en vivo...")

        while self.is_running:
            try:
                # 1. Obtener estado oficial de Binance
                # None  = API falló (red/rate-limit) → no hacer BINANCE_SYNC, usar precio local
                # {}    = API OK, cero posiciones en Binance → posición cerrada externamente
                # {sym} = API OK, posición activa → usar datos reales
                official_details = None
                if self.trader:
                    official_details = await self.trader.get_active_positions_details()

                # 2. Obtener posiciones locales y auditarlas
                query_positions = "SELECT * FROM positions"
                async with self.db.pool.acquire() as conn:
                    positions = await conn.fetch(query_positions)

                for pos in positions:
                    await self._check_position(pos, official_details)

                # 2. Dormir el intervalo configurado
                await asyncio.sleep(self.MONITOR_INTERVAL_SECONDS)

            except Exception as e:
                print(f"⚠️ [MONITOR] Error en ciclo de vigilancia: {e}")
                await asyncio.sleep(5)

    async def _check_position(self, pos: Dict[str, Any], official_details) -> None:
        """
        Audita una posición individual contra el mercado actual.

        official_details:
          None  → Binance no respondió (error de red/rate-limit).
                  Usar precio local para actualizar PnL. NO hacer BINANCE_SYNC.
          {}    → Binance respondió OK pero no tiene esta posición abierta.
                  La posición se cerró externamente (TP/SL hit). Hacer BINANCE_SYNC.
          {sym} → Binance tiene la posición activa. Usar datos reales.
        """
        symbol = pos['symbol']
        side = pos['side']
        entry_price = float(pos['entry_price'])
        qty = float(pos['quantity'])

        official = (official_details or {}).get(symbol) if official_details is not None else None

        if official:
            # Caso A: Binance confirma posición activa — datos reales
            current_price = official['mark_price']
            pnl_unrealized = official['pnl']

        elif official_details is not None and symbol not in official_details:
            # Caso B: El fetch general no incluye el símbolo.
            # VERIFICACIÓN DIRECTA antes de BINANCE_SYNC para evitar falsos positivos
            # (fetch_positions() sin args puede retornar incompleto en Binance).
            _log(f"⚠️ {symbol} ausente en fetch general — verificando directamente en Binance...")
            if self.trader:
                still_open = await self.trader.check_position_exists(symbol)
                if still_open:
                    _log(
                        f"⚠️ {symbol} CONFIRMADA activa en query directo — "
                        f"fetch general incompleto. Ignorando BINANCE_SYNC."
                    )
                    return
            # Confirmado cerrada en Binance → sincronizar BD
            _log(f"📡 [MONITOR] {symbol} confirmada cerrada en Binance. Sincronizando...")
            await self._close_position(pos, 0.0, float(pos['pnl_unrealized'] or 0), "BINANCE_SYNC")
            return

        else:
            # Caso C: Binance falló (official_details is None) — precio local como fallback
            query_price = '''
                SELECT close FROM market_data
                WHERE symbol = $1 ORDER BY open_time DESC LIMIT 1
            '''
            async with self.db.pool.acquire() as conn:
                current_price_val = await conn.fetchval(query_price, symbol)

            if not current_price_val:
                return

            current_price = float(current_price_val)
            if side == 'BUY':
                pnl_unrealized = (current_price - entry_price) * qty
            else:
                pnl_unrealized = (entry_price - current_price) * qty

        invested_usdt = float(pos['invested_usdt'] or (qty * entry_price))
        tp = float(pos['take_profit'])
        sl = float(pos['stop_loss'])

        # Actualizar precio actual y PnL en la tabla positions
        query_update_pos = '''
            UPDATE positions 
            SET current_price = $1, pnl_unrealized = $2, updated_at = NOW() 
            WHERE id = $3
        '''
        async with self.db.pool.acquire() as conn:
            await conn.execute(
                query_update_pos, current_price, pnl_unrealized, pos['id']
            )

        # 3. Verificar condiciones de cierre (TP, SL o LIQUIDACIÓN)
        should_close = False
        reason = ""

        # ESCUDO DE CAPITAL: Liquidación preventiva antes del 100%
        shield_trigger = -(invested_usdt * self.CAPITAL_SHIELD_THRESHOLD)
        if pnl_unrealized <= shield_trigger:
            should_close = True
            reason = (
                f"ESCUDO_CAPITAL: Liquidación preventiva "
                f"({int(self.CAPITAL_SHIELD_THRESHOLD*100)}% Margen)"
            )

        if not should_close:
            if side == 'BUY':
                if current_price >= tp:
                    should_close = True
                    reason = "TAKE PROFIT"
                elif current_price <= sl:
                    should_close = True
                    reason = "STOP LOSS"
            else:  # SELL
                if current_price <= tp:
                    should_close = True
                    reason = "TAKE PROFIT"
                elif current_price >= sl:
                    should_close = True
                    reason = "STOP LOSS"

        if should_close:
            await self._close_position(
                pos, current_price, pnl_unrealized, reason
            )

    async def _close_position(
        self, pos: Dict[str, Any], close_price: float, 
        final_pnl: float, reason: str
    ) -> None:
        """
        Cierra la posición en el mercado real (si es necesario) 
        y libera el capital en la base de datos local.
        """
        symbol = pos['symbol']
        _log(
            f"💰 Iniciando cierre de {symbol} | "
            f"Razón: {reason} | PnL Est.: ${final_pnl:.2f}"
        )

        # 1. EJECUCIÓN EN EXCHANGE (Solo si no fue un cierre detectado por Sincronización)
        if self.trader and reason != "BINANCE_SYNC":
            quantity = float(pos['quantity'])
            side = pos['side']
            success = await self.trader.close_position_on_exchange(symbol, quantity, side)
            if not success:
                # Si Binance rechazó el cierre, NO tocar la BD — el monitor reintentará
                # en el próximo ciclo (1s). Sin este abort, la posición quedaría abierta
                # en Binance pero borrada en la BD ("posición fantasma").
                _log(
                    f"❌ FALLO al cerrar {symbol} en Binance (razón: {reason}). "
                    f"BD local NO modificada — reintentando en el próximo ciclo."
                )
                return

        invested_amount = float(pos.get('invested_usdt', 0.0))
        leverage = float(pos.get('leverage', 1.0))
        quantity = float(pos['quantity'])

        # Descontar fee de cierre (taker) del PnL bruto para mostrar ganancia neta real.
        # La fee de apertura ya fue cobrada por Binance al wallet en el momento del open.
        # Solo descontamos si tenemos un precio de cierre real (no en BINANCE_SYNC con 0.0).
        effective_close = close_price if close_price > 0 else float(pos.get('current_price', 0.0))
        if effective_close > 0:
            close_fee = effective_close * quantity * BINANCE_FUTURES_TAKER_FEE
            net_pnl = final_pnl - close_fee
        else:
            net_pnl = final_pnl

        async with self.db.pool.acquire() as conn:
            async with conn.transaction():
                # 1. Eliminar de posiciones abiertas
                await conn.execute(
                    "DELETE FROM positions WHERE id = $1", pos['id']
                )

                # 2. Registrar en el historial de trades finalizado
                query_trade = '''
                    INSERT INTO trades
                        (symbol, side, order_type, quantity, price, total,
                         pnl, leverage, invested_usdt, status, executed_at)
                    VALUES ($1, $2, 'MARKET', $3, $4, $5, $6, $7, $8,
                            'CLOSED', NOW())
                '''
                await conn.execute(
                    query_trade, pos['symbol'], pos['side'], quantity,
                    close_price, quantity * close_price, net_pnl,
                    leverage, invested_amount
                )

                # 3. Sincronizar Portafolio (Liberar Margen + Sumar PnL neto)
                await self.db.sync_portfolio_on_trade(
                    invested_amount, 'CLOSE', net_pnl
                )
                _log(
                    f"✅ {symbol} cerrada y registrada | "
                    f"PnL neto: ${net_pnl:.2f} | Margen liberado: ${invested_amount:.2f}"
                )

    async def manual_close_position(self, symbol: str) -> bool:
        """Cierre forzado a petición del Operador. Garantiza que la orden llegue a Binance."""
        query = "SELECT * FROM positions WHERE symbol = $1"
        async with self.db.pool.acquire() as conn:
            pos = await conn.fetchrow(query, symbol)

        if not pos:
            return False

        _log(f"🎯 Cierre manual solicitado para {symbol} — consultando estado en Binance...")

        current_price = 0.0
        pnl = 0.0

        # 1. Consultar estado en Binance
        official_details = None
        if self.trader:
            official_details = await self.trader.get_active_positions_details()

        if official_details is None:
            # Binance no respondió — abortar para no dejar posición zombie
            _log(f"❌ Cierre de {symbol} ABORTADO: Binance no respondió. Intenta de nuevo.")
            return False

        official = official_details.get(symbol)

        if official:
            # Posición activa en Binance — tomar precio y PnL oficial
            current_price = official['mark_price']
            pnl = official['pnl']
            _log(
                f"📡 {symbol} confirmada en Binance | "
                f"Mark Price: {current_price} | PnL: ${pnl:.2f}"
            )
        else:
            # Binance no tiene la posición — ya cerró externamente (TP/SL hit)
            _log(f"📡 {symbol} ya no está en Binance (cerró por TP/SL). Sincronizando BD...")
            await self._close_position(
                pos, float(pos['pnl_unrealized'] or 0.0),
                float(pos['pnl_unrealized'] or 0.0), "BINANCE_SYNC"
            )
            return True

        # 2. Enviar orden de cierre a Binance y limpiar BD
        await self._close_position(pos, current_price, pnl, "MANUAL_USER")
        return True

    def stop(self) -> None:
        """Detiene el ciclo de vigilancia seguro."""
        self.is_running = False
