"""
SysMho — Circuit Breaker de Autonomía.

Protección de capital dura: evalúa condiciones sistémicas antes de que
el MetaEvaluator apruebe cualquier operación autónoma.

Si cualquier condición se activa → bloqueo total hasta el reset horario/diario.
"""

import os
from datetime import datetime, timezone
from typing import Tuple, List


# ---- Parámetros desde .env (con defaults conservadores) ---- #
def _env_float(key: str, default: float) -> float:
    try:
        return float(os.getenv(key, str(default)))
    except ValueError:
        return default


def _env_int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except ValueError:
        return default


MAX_OPEN_POSITIONS      = _env_int('CB_MAX_POSITIONS', 3)
MAX_DAILY_TRADES        = _env_int('CB_MAX_DAILY_TRADES', 8)
MAX_CONSECUTIVE_LOSSES  = _env_int('CB_MAX_CONSEC_LOSSES', 3)
DAILY_LOSS_LIMIT_PCT    = _env_float('CB_DAILY_LOSS_PCT', 0.04)   # 4% del capital
WEEKLY_DRAWDOWN_PCT     = _env_float('CB_WEEKLY_DRAWDOWN_PCT', 0.08)  # 8% del capital


class CircuitBreaker:
    """
    Evalúa si las condiciones sistémicas permiten operar.

    Checks (en orden de severidad):
      1. Drawdown diario  ≥ CB_DAILY_LOSS_PCT  → stop del día
      2. Drawdown semanal ≥ CB_WEEKLY_DRAWDOWN_PCT → stop de la semana
      3. Pérdidas consecutivas ≥ CB_MAX_CONSEC_LOSSES → pausa
      4. Posiciones abiertas ≥ CB_MAX_POSITIONS → no más entradas
      5. Trades del día ≥ CB_MAX_DAILY_TRADES → límite operativo
    """

    def check(
        self,
        open_positions: int,
        daily_trades: int,
        consecutive_losses: int,
        daily_pnl_pct: float,
        weekly_pnl_pct: float,
    ) -> Tuple[bool, str]:
        """
        Evalúa todas las condiciones.

        Returns:
            (triggered: bool, reason: str)
            triggered=True significa BLOQUEO — no operar.
        """
        # 1. Drawdown diario
        if daily_pnl_pct <= -abs(DAILY_LOSS_LIMIT_PCT):
            return True, (
                f"🛑 Drawdown diario {daily_pnl_pct*100:.2f}% excede límite "
                f"{DAILY_LOSS_LIMIT_PCT*100:.1f}%"
            )

        # 2. Drawdown semanal
        if weekly_pnl_pct <= -abs(WEEKLY_DRAWDOWN_PCT):
            return True, (
                f"🛑 Drawdown semanal {weekly_pnl_pct*100:.2f}% excede límite "
                f"{WEEKLY_DRAWDOWN_PCT*100:.1f}%"
            )

        # 3. Pérdidas consecutivas
        if consecutive_losses >= MAX_CONSECUTIVE_LOSSES:
            return True, (
                f"⚠️ {consecutive_losses} pérdidas consecutivas "
                f"(límite: {MAX_CONSECUTIVE_LOSSES})"
            )

        # 4. Posiciones abiertas
        if open_positions >= MAX_OPEN_POSITIONS:
            return True, (
                f"⚠️ {open_positions} posiciones abiertas "
                f"(máximo: {MAX_OPEN_POSITIONS})"
            )

        # 5. Trades diarios
        if daily_trades >= MAX_DAILY_TRADES:
            return True, (
                f"⚠️ {daily_trades} operaciones hoy "
                f"(límite diario: {MAX_DAILY_TRADES})"
            )

        return False, ""

    def describe(self) -> dict:
        """Devuelve los parámetros activos (para dashboard)."""
        return {
            "max_positions": MAX_OPEN_POSITIONS,
            "max_daily_trades": MAX_DAILY_TRADES,
            "max_consec_losses": MAX_CONSECUTIVE_LOSSES,
            "daily_loss_pct": DAILY_LOSS_LIMIT_PCT,
            "weekly_drawdown_pct": WEEKLY_DRAWDOWN_PCT,
        }
