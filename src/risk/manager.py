"""
SysMho — Gestor de Riesgos.

Audita las señales de la IA antes de permitir que se ejecuten.
Aplica reglas estrictas de Position Sizing, Notional Cap,
y control de volatilidad usando el ATR.
"""

from typing import Dict, Any, Optional

from src.constants import NOTIONAL_CAP_RATIO, EXPOSURE_LIMIT_RATIO
from src.database.repository import DatabaseRepository


class RiskManager:
    """Auditor de Riesgo Matemático y Volatilidad."""

    # Constantes operativas de capital (sincronizadas con src/constants.py)
    MIN_NOTIONAL = 6.0
    NOTIONAL_CAP_RATIO = NOTIONAL_CAP_RATIO
    EXPOSURE_LIMIT_RATIO = EXPOSURE_LIMIT_RATIO

    def __init__(
        self,
        max_risk_per_trade: float = 0.02,
        atr_multiplier_sl: float = 1.5,
        atr_multiplier_tp: float = 3.0,
        aggressive_mode: bool = False,
        db: Optional[DatabaseRepository] = None
    ) -> None:
        """
        Inicializa el perfil de riesgo.

        Args:
            max_risk_per_trade: % máximo del portafolio a perder (0.02 = 2%).
            atr_multiplier_sl: Margen Stop Loss en Volatilidad (ATR).
            atr_multiplier_tp: Margen Take Profit (ej: 3.0 para R/B 1:2).
            aggressive_mode: Si es True, sube el riesgo y ajusta ratios.
            db: Repositorio de BD.
        """
        if aggressive_mode:
            self.max_risk_per_trade = 0.05
            self.atr_multiplier_sl = 1.0
            self.atr_multiplier_tp = 2.5
        else:
            self.max_risk_per_trade = max_risk_per_trade
            self.atr_multiplier_sl = atr_multiplier_sl
            self.atr_multiplier_tp = atr_multiplier_tp

        self.db = db if db else DatabaseRepository()

    async def evaluate_signal(
        self, symbol: str, signal_data: Dict[str, Any],
        current_market: Dict[str, Any], portfolio_balance: float
    ) -> Dict[str, Any]:
        """
        Audita una señal y calcula su proyección financiera exacta.

        Args:
            symbol: El par evaluado.
            signal_data: Dict entregado por ModelPredictor.
            current_market: Última vela con indicadores en crudo.
            portfolio_balance: Saldo USDT actual en Futuros.
        """
        signal_int = signal_data.get('signal_int', 0)
        confidence = signal_data.get('confidence', 0.0)
        raw_probs = signal_data.get('raw_probs', [0.0, 1.0, 0.0])

        # Probabilidades [ SELL, WAIT, BUY ]
        if signal_int == 1:
            win_prob = raw_probs[2]
            loss_prob = raw_probs[0]
        elif signal_int == -1:
            win_prob = raw_probs[0]
            loss_prob = raw_probs[2]
        else:
            win_prob = 0.0
            loss_prob = 0.0

        # REGLA 1: Descartar si el filtro es Neutral
        if signal_int == 0:
            reason = (
                f"{signal_data.get('signal_str', 'WAIT')} "
                "- Señal anulada: Es Lateral/Neutral."
            )
            await self._log_to_db(
                signal_data.get('signal_type', 'PREMIUM'),
                symbol, reason, False, confidence
            )
            return {'approved': False, 'reason': reason}

        current_price = current_market['close']
        atr = current_market['atr_14']

        # Cálculo Dinámico Científico
        sl_distance = atr * self.atr_multiplier_sl
        tp_distance = atr * self.atr_multiplier_tp

        if signal_int == 1:  # COMPRAR (Long)
            # Escudo: No menos del 10% del precio
            stop_loss = max(current_price * 0.9, current_price - sl_distance)
            take_profit = current_price + tp_distance
        else:  # VENDER (Short)
            stop_loss = current_price + sl_distance
            # Escudo: TP de short no baja más del 10% del precio de entrada
            take_profit = max(current_price * 0.90, current_price - tp_distance)

        # REGLA 2: Position Sizing Geométrico
        max_usd_loss_allowed = portfolio_balance * self.max_risk_per_trade

        if sl_distance <= 0:
            reason = "Señal anulada: Volatilidad nula (ATR <= 0)."
            await self._log_to_db(
                signal_data['signal_str'], symbol, reason, False, confidence
            )
            return {'approved': False, 'reason': reason}

        position_size_crypto = max_usd_loss_allowed / sl_distance
        position_size_usdt = position_size_crypto * current_price

        # REGLA 3: Control de Liquidez y Escudo de Capital
        try:
            query = (
                "SELECT in_positions, total_balance FROM portfolio "
                "ORDER BY recorded_at DESC LIMIT 1"
            )
            async with self.db.pool.acquire() as conn:
                p_record = await conn.fetchrow(query)

            total_cap = float(p_record['total_balance']) if p_record \
                else portfolio_balance
            current_in_play = float(p_record['in_positions']) if p_record \
                else 0.0

            # Si el cap es 0, usamos balance binance como techo
            if total_cap <= 0:
                total_cap = portfolio_balance

            notional_cap = portfolio_balance * self.NOTIONAL_CAP_RATIO

            # Verificación del umbral mínimo de Binance
            if position_size_usdt < self.MIN_NOTIONAL:
                # Escalar si hay margen de maniobra
                if (current_in_play + self.MIN_NOTIONAL) <= total_cap:
                    position_size_usdt = self.MIN_NOTIONAL
                    position_size_crypto = position_size_usdt / current_price
                    print(
                        f"⚠️ [RIESGO] Ajustando Notional al mínimo "
                        f"permitido: {self.MIN_NOTIONAL} USDT"
                    )
                else:
                    reason = (
                        f"Señal anulada: Monto ({position_size_usdt:.2f} "
                        "USDT) insuficiente y sin capacidad de maniobra."
                    )
                    await self._log_to_db(
                        signal_data.get('signal_str', 'WAIT'),
                        symbol, reason, False, confidence
                    )
                    return {'approved': False, 'reason': reason}

            # Supervivencia estricta: CCXT fallará con < 5.0
            if position_size_usdt < 5.1:
                reason = "Señal anulada: Notional inviable para el exchange."
                await self._log_to_db(
                    signal_data.get('signal_str', 'WAIT'),
                    symbol, reason, False, confidence
                )
                return {'approved': False, 'reason': reason}

            if (position_size_usdt > notional_cap and
                    notional_cap >= self.MIN_NOTIONAL):
                position_size_usdt = notional_cap
                position_size_crypto = position_size_usdt / current_price
                print(
                    f"⚠️ [RIESGO] Recortado por Notional Cap "
                    f"(Max 12%): {position_size_usdt:.2f} USDT"
                )

            exposure_warning = (
                (current_in_play + position_size_usdt) >
                (total_cap * self.EXPOSURE_LIMIT_RATIO)
            )

            if exposure_warning:
                reason = (
                    f"Señal rechazada: Exposición total superaría el "
                    f"{int(self.EXPOSURE_LIMIT_RATIO * 100)}% del capital."
                )
                await self._log_to_db(
                    signal_data.get('signal_str', 'WAIT'),
                    symbol, reason, False, confidence
                )
                return {'approved': False, 'reason': reason}

        except Exception as e:
            print(f"⚠️ Error al calcular límites de exposición: {e}")
            position_size_usdt = portfolio_balance * self.NOTIONAL_CAP_RATIO
            position_size_crypto = position_size_usdt / current_price
            exposure_warning = False

        # PROYECCIONES FINANCIERAS
        potential_profit_usdt = position_size_crypto * tp_distance
        potential_loss_usdt = position_size_crypto * sl_distance

        # APROBADO
        result = {
            'approved': True,
            'reason': "Auditada",
            'symbol': symbol,
            'side': signal_data['signal_str'],
            'entry_price': current_price,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'quantity': position_size_crypto,
            'invested_usdt': position_size_usdt,
            'confidence': confidence,
            'win_probability': win_prob,
            'loss_probability': loss_prob,
            'potential_profit_usdt': potential_profit_usdt,
            'potential_loss_usdt': potential_loss_usdt,
            'exposure_warning': bool(exposure_warning)
        }

        log_reason = f"{signal_data['signal_str']} - Aprobada"
        if exposure_warning:
            log_reason += " (⚠️ Riesgo Exposición)"

        await self._log_to_db(
            signal_data.get('signal_type', 'PREMIUM'),
            symbol, log_reason, True, confidence
        )
        return result

    async def _log_to_db(
        self, signal_type: str, symbol: str, reason: str,
        approved: bool, risk_score: float
    ) -> None:
        """Registra el proceso de auditoría en Base de Datos."""
        query = '''
            INSERT INTO risk_log
                (signal_type, symbol, reason, approved, risk_score)
            VALUES ($1, $2, $3, $4, $5)
        '''
        async with self.db.pool.acquire() as conn:
            await conn.execute(
                query, signal_type, symbol, reason,
                approved, float(risk_score)
            )
