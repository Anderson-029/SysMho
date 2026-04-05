"""
SysMho — Ejecutor de Órdenes (Trader).

Puente final de comunicación con Binance. Ejecuta las órdenes
auditadas e inserta el registro transaccional exacto
(fees, notional efectivo, price slip) en la base de datos.
"""

import time
from typing import Dict, Any, Optional

import ccxt.async_support as ccxt

from config.settings import (
    BINANCE_API_KEY,
    BINANCE_SECRET_KEY,
    BINANCE_TESTNET
)
from src.constants import MIN_NOTIONAL_USDT
from src.database.repository import DatabaseRepository
from src.paths import BRAIN_LOG as _BRAIN_LOG


def _log(msg: str) -> None:
    """Escribe evento crítico en el log neuronal visible en el dashboard."""
    line = f"[{time.strftime('%H:%M:%S')}] [TRADER] {msg}\n"
    try:
        with open(_BRAIN_LOG, "a", encoding="utf-8") as f:
            f.write(line)
            f.flush()
    except Exception:
        pass
    print(line.rstrip())


class TradeExecutor:
    """Clase encargada de interactuar directamente de forma segura con CCXT."""

    # Margen de seguridad sobre los 5.0 USDT mínimos de Binance (fuente: constants.py)
    MIN_NOTIONAL_SAFE = MIN_NOTIONAL_USDT

    def __init__(self, db: Optional[DatabaseRepository] = None) -> None:
        """Inicializa la API configurando el entorno Testnet/Mainnet."""
        self.exchange = ccxt.binance({
            'apiKey': BINANCE_API_KEY,
            'secret': BINANCE_SECRET_KEY,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future',
                'adjustForTimeDifference': True
            }
        })
        if BINANCE_TESTNET:
            self.exchange.enable_demo_trading(True)

        self.db = db if db else DatabaseRepository()
        self._api_status: str = "UNKNOWN"
        self._connection_retries: int = 0

    @property
    def api_status(self) -> str:
        """Estado público del enlace con Binance."""
        return self._api_status

    async def check_api_link(self) -> bool:
        """
        [ESCUDO API] Verifica activamente el estado del enlace con Binance (Health Monitor).
        Gestiona explícitamente los estados ACTIVE, RECONNECTING y DISCONNECTED.
        """
        # Si el status previo es un error o desconocido, asumimos transición a RECONNECTING.
        if self._api_status not in ["ACTIVE"]:
            # Solo cambiamos a RECONNECTING si no estamos explícitamente DISCONNECTED de forma fatal (ej: llaves malas)
            if self._api_status != "DISCONNECTED" or self._connection_retries < 3:
                self._api_status = "RECONNECTING"

        try:
            await self.exchange.fetch_balance()
            if self._api_status != "ACTIVE":
                print("✅ [CONEXIÓN] Enlace Seguro con Binance restablecido.")
            self._api_status = "ACTIVE"
            self._connection_retries = 0
            return True
        except Exception as e:
            err_str = str(e)
            if "Invalid API-key" in err_str or "-2015" in err_str:
                self._api_status = "INVALID_KEYS"
                print("🚨 [SISTEMA CRÍTICO] Llaves API inválidas o expiradas. Enlace Roto.")
            else:
                self._connection_retries += 1
                self._api_status = "RECONNECTING"
                print(f"⚠️ [CONEXIÓN] Red caída o inaccesible, reconectando... ({self._connection_retries}) | Error: {e}")
            return False

    async def execute_trade(
        self, risk_approved_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Dispara los misiles reales hacia Binance tras ser auditado.
        """
        symbol = risk_approved_data['symbol']
        side = risk_approved_data['side'].upper()
        quantity = risk_approved_data['quantity']
        price = risk_approved_data['entry_price']
        stop_loss = risk_approved_data['stop_loss']
        take_profit = risk_approved_data['take_profit']
        invested_usdt = float(risk_approved_data.get('invested_usdt', 0.0))

        # --- MARGIN CHECK ---
        current_balance = await self.get_portfolio_balance()
        if current_balance < invested_usdt:
            _log(
                f"❌ Fondos insuficientes para {symbol}. "
                f"Req: ${invested_usdt:.2f} | Disponible: ${current_balance:.2f}"
            )
            return {
                'success': False,
                'error': f"Saldo insuficiente (${current_balance:.2f})"
            }

        try:
            # Cargar/recargar mercados para conversión de precisión
            if not self.exchange.markets or symbol not in self.exchange.markets:
                await self.exchange.load_markets(True)

            formatted_qty = float(
                self.exchange.amount_to_precision(symbol, quantity)
            )
            formatted_price = float(
                self.exchange.price_to_precision(symbol, price)
            )

            # --- FINAL NOTIONAL CHECK ---
            notional = formatted_qty * formatted_price
            print(
                f"🔍 [DEBUG] Validando Orden: Qty({formatted_qty}) * "
                f"Price({formatted_price}) = Notional({notional:.2f} USDT)"
            )

            if notional < self.MIN_NOTIONAL_SAFE:
                print(
                    f"❌ [TRADER] Bloqueo Notional Insuficiente "
                    f"para {symbol}: {notional:.2f} USDT"
                )
                return {
                    'success': False,
                    'error': f"Notional insuficiente ({notional:.2f} USDT)."
                }

            if formatted_qty <= 0:
                print(
                    f"❌ [TRADER] Bloqueo de Cantidad Cero/Inválida "
                    f"para {symbol}."
                )
                return {
                    'success': False,
                    'error': 'Cantidad demasiado pequeña (Binance Rules).'
                }

            _log(
                f"🚀 DISPARANDO ORDEN: {side} {formatted_qty} {symbol} "
                f"@ ~{formatted_price} | Notional: {notional:.2f} USDT"
            )

            # 1. INGRESO AL MERCADO
            order = await self.exchange.create_order(
                symbol=symbol,
                type='market',
                side=side,
                amount=formatted_qty
            )

            _log(f"✅ ORDEN CONFIRMADA por Binance — ID: #{order['id']} | {symbol}")

            # 2. COLOCACIÓN DE REDES DE SEGURIDAD (SL/TP)
            sl_side = 'SELL' if side == 'BUY' else 'BUY'

            try:
                sl_price = float(
                    self.exchange.price_to_precision(symbol, stop_loss)
                )
                await self.exchange.create_order(
                    symbol=symbol,
                    type='STOP_MARKET',
                    side=sl_side,
                    amount=formatted_qty,
                    params={'stopPrice': sl_price, 'reduceOnly': True}
                )
                _log(f"🛡️ Stop Loss colocado en {sl_price} para {symbol}")
            except Exception as e:
                _log(f"⚠️ FALLO al colocar Stop Loss en {symbol}: {e}")

            try:
                tp_price = float(
                    self.exchange.price_to_precision(symbol, take_profit)
                )
                await self.exchange.create_order(
                    symbol=symbol,
                    type='TAKE_PROFIT_MARKET',
                    side=sl_side,
                    amount=formatted_qty,
                    params={'stopPrice': tp_price, 'reduceOnly': True}
                )
                _log(f"🎯 Take Profit colocado en {tp_price} para {symbol}")
            except Exception as e:
                _log(f"⚠️ FALLO al colocar Take Profit en {symbol}: {e}")

            # 3. REGISTRO CONTABLE REAL
            total_value = formatted_qty * formatted_price
            exec_price = float(order.get('average', formatted_price))

            # Obtener leverage real de la posición recién abierta
            actual_leverage = 1.0
            try:
                open_positions = await self.exchange.fetch_positions([symbol])
                for pos in open_positions:
                    pos_symbol = pos['symbol'].split(':')[0]
                    if pos_symbol == symbol:
                        actual_leverage = float(pos.get('leverage', 1.0))
                        break
            except Exception:
                pass  # Mantener 1.0 si falla la consulta

            await self._log_trade(
                symbol, side, 'MARKET', formatted_qty, exec_price,
                total_value, 'XGBoost_v1_IA', take_profit, stop_loss,
                invested_usdt, actual_leverage, order['id']
            )

            # 4. BLOQUEO DE CAPITAL
            await self.db.sync_portfolio_on_trade(invested_usdt, 'OPEN')

            return {
                'success': True,
                'order_id': order['id'],
                'executed_price': exec_price
            }

        except Exception as e:
            _log(f"❌ ERROR FATAL comunicándose con Binance para {symbol}: {e}")
            return {'success': False, 'error': str(e)}

    async def get_portfolio_balance(self) -> float:
        """Saca el balance 100% de Binance (Sincronización Real Absoluta)."""
        try:
            balance = await self.exchange.fetch_balance()
            info = balance.get('info', {})
            return float(info.get('availableBalance', balance['free'].get('USDT', 0.0)))
        except Exception as e:
            print(f"❌ [TRADER] Error obteniendo balance real de Binance: {e}")
            return 0.0

    async def get_active_positions_details(self) -> Optional[Dict[str, Any]]:
        """
        Obtiene el estado oficial de todas las posiciones abiertas en Binance.
        Retorna un diccionario indexado por símbolo con PnL y Mark Price.

        CRÍTICO: Retorna None si la llamada a Binance falla (red, rate limit, etc.)
        El monitor DEBE distinguir entre "sin posiciones" ({}) y "llamada fallida" (None)
        para no limpiar la BD cuando Binance simplemente no respondió.
        """
        try:
            positions = await self.exchange.fetch_positions()
            details = {}
            for pos in positions:
                amt = float(pos.get('contracts', 0) or pos.get('amount', 0))
                if amt != 0:
                    full_symbol = pos['symbol']
                    symbol = full_symbol.split(':')[0]
                    details[symbol] = {
                        'pnl': float(pos.get('unrealizedPnl', 0.0)),
                        'mark_price': float(pos.get('markPrice', 0.0)),
                        'entry_price': float(pos.get('entryPrice', 0.0)),
                        'leverage': float(pos.get('leverage') or 1.0),
                        'side': 'BUY' if amt > 0 else 'SELL',
                        'quantity': abs(amt),
                        'collateral': float(pos.get('initialMargin', 0.0))
                    }
            return details
        except Exception as e:
            print(f"⚠️ [TRADER] Fallo al consultar posiciones en Binance (se omite ciclo): {e}")
            return None  # None = fallo de red, NO confundir con {} = sin posiciones abiertas

    async def check_position_exists(self, symbol: str) -> bool:
        """
        Verifica si una posición específica está activa en Binance.
        Usa fetch_positions([symbol]) — más confiable que el fetch general sin args.

        Returns:
            True  → posición confirmada activa (o no se pudo verificar — safe default)
            False → posición confirmada cerrada
        """
        try:
            positions = await self.exchange.fetch_positions([symbol])
            for pos in positions:
                amt = float(pos.get('contracts', 0) or pos.get('amount', 0))
                if amt != 0:
                    sym = pos['symbol'].split(':')[0]
                    if sym == symbol:
                        return True
            return False
        except Exception as e:
            # Si Binance no responde, asumimos que existe — nunca cerrar BD sin certeza
            _log(f"⚠️ Error verificando {symbol} en Binance: {e} — asumiendo activa (safe)")
            return True

    async def close_position_on_exchange(
        self, symbol: str, quantity: float, side: str
    ) -> bool:
        """
        Cierra una posición de manera ULTRA-RÁPIDA cancelando redes y cerrando a mercado.
        Optimizado para Dinero Real (Sub-second execution).
        """
        try:
            # 1. CANCELAR TODAS las órdenes del símbolo (Seguridad Crítica)
            # Esto elimina SL/TP previos para evitar que queden activos.
            try:
                await self.exchange.cancel_all_orders(symbol)
                _log(f"🛡️ Órdenes SL/TP de {symbol} canceladas antes del cierre.")
            except Exception as e:
                _log(f"⚠️ Aviso al cancelar órdenes de {symbol}: {e}")

            # 2. EJECUTAR CIERRE INMEDIATO A MERCADO
            # Usamos dirección opuesta a la posición actual
            side_to_close = 'SELL' if side.upper() == 'BUY' else 'BUY'

            _log(f"⚔️ ENVIANDO CIERRE a Binance: {side_to_close} {quantity} {symbol} (reduceOnly)")

            close_order = await self.exchange.create_order(
                symbol=symbol,
                type='market',
                side=side_to_close,
                amount=quantity,
                params={'reduceOnly': True}
            )

            _log(f"✅ CIERRE CONFIRMADO por Binance — ID: #{close_order['id']} | {symbol} CERRADA.")
            return True

        except Exception as e:
            err_str = str(e)
            # ReduceOnly rechazado = la posición en Binance tiene un lado diferente al esperado.
            # NO interpretar como "posición ya cerrada" — retornar False para que el monitor
            # NO limpie la BD. El siguiente ciclo del monitor detectará el SIDE_MISMATCH
            # y corregirá el lado antes de intentar el cierre nuevamente.
            if "-2022" in err_str or "ReduceOnly Order is rejected" in err_str:
                _log(
                    f"❌ {symbol}: ReduceOnly rechazado — posición abierta en Binance con side "
                    f"diferente al registrado en BD. BD no modificada. El monitor corregirá el mismatch."
                )
                return False
            _log(f"❌ FALLO CRÍTICO cerrando {symbol} en Binance: {e}")
            return False

    async def _log_trade(
        self, symbol: str, side: str, order_type: str, quantity: float,
        price: float, total: float, signal_source: str,
        take_profit: Optional[float] = None,
        stop_loss: Optional[float] = None,
        invested_usdt: float = 0.0,
        leverage: float = 1.0,
        order_id: Optional[str] = None
    ) -> None:
        """Registra el trade y actualiza las posiciones abiertas."""
        query_history = '''
            INSERT INTO trades 
                (symbol, side, order_type, quantity, price, total, 
                 signal_source, status, leverage, invested_usdt, order_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7, 'EXECUTED', $8, $9, $10)
        '''

        query_position = '''
            INSERT INTO positions 
                (symbol, side, entry_price, quantity, stop_loss, 
                 take_profit, current_price, pnl_unrealized, 
                 invested_usdt, leverage)
            VALUES ($1, $2, $3, $4, $5, $6, $3, 0, $7, $8)
            ON CONFLICT (symbol) DO UPDATE SET
                side = EXCLUDED.side,
                entry_price = EXCLUDED.entry_price,
                quantity = EXCLUDED.quantity,
                stop_loss = EXCLUDED.stop_loss,
                take_profit = EXCLUDED.take_profit,
                current_price = EXCLUDED.entry_price,
                pnl_unrealized = 0,
                invested_usdt = EXCLUDED.invested_usdt,
                leverage = EXCLUDED.leverage,
                opened_at = NOW();
        '''

        async with self.db.pool.acquire() as conn:
            try:
                # Transacción Atómica
                async with conn.transaction():
                    await conn.execute(
                        query_history, symbol, side, order_type, quantity,
                        price, total, signal_source, leverage,
                        invested_usdt, order_id
                    )

                    if take_profit and stop_loss and stop_loss > 0:
                        await conn.execute(
                            query_position, symbol, side, price, quantity,
                            stop_loss, take_profit, invested_usdt, leverage
                        )
            except Exception as e:
                print(f"❌ [DB ERROR] Falló indexación trade {symbol}: {e}")
                raise e

    async def close_connection(self) -> None:
        """Desconecta el websocket socket de CCXT de manera amable."""
        await self.exchange.close()
