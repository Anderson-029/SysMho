"""
SysMho — Rutas del Sistema de Autonomía.

Expone endpoints para:
  - Estado del modo autónomo (activo/inactivo, parámetros CB)
  - Historial de decisiones autónomas
  - Toggle runtime del modo autónomo
  - Estadísticas del SelfLearner
"""

import os
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException

from src.dashboard.deps import db
from src.runtime_config import is_autonomous, set_autonomous, reset_circuit_breaker

_BRAIN_LOG = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    'sysmho_brain.log'
)

def _log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime('%H:%M:%S')
    line = f"[{ts}] {msg}"
    try:
        with open(_BRAIN_LOG, 'a', encoding='utf-8') as f:
            f.write(line + '\n')
    except Exception:
        pass

router = APIRouter(prefix="/api/autonomous", tags=["Autonomous"])


@router.get("/status")
async def get_autonomous_status():
    """Estado actual del sistema autónomo y parámetros del CircuitBreaker."""
    from src.executor.circuit_breaker import CircuitBreaker
    cb = CircuitBreaker()

    # Estadísticas del día para mostrar en el dashboard
    try:
        stats = await db.get_daily_stats()
    except Exception:
        stats = {
            'trades_today': 0,
            'daily_pnl_pct': 0.0,
            'weekly_pnl_pct': 0.0,
            'consecutive_losses': 0,
            'total_balance': 0.0,
        }

    # Contar posiciones abiertas
    try:
        async with db.pool.acquire() as conn:
            open_positions = await conn.fetchval("SELECT COUNT(*) FROM positions") or 0
    except Exception:
        open_positions = 0

    # Estado del circuit breaker
    cb_triggered, cb_reason = cb.check(
        open_positions=int(open_positions),
        daily_trades=stats.get('trades_today', 0),
        consecutive_losses=stats.get('consecutive_losses', 0),
        daily_pnl_pct=stats.get('daily_pnl_pct', 0.0),
        weekly_pnl_pct=stats.get('weekly_pnl_pct', 0.0),
    )

    # Stats del SelfLearner
    try:
        from src.ai.self_learner import SelfLearner
        learner = SelfLearner()
        learner_summary = learner.summary()
    except Exception:
        learner_summary = {}

    return {
        'autonomous_mode': is_autonomous(),
        'circuit_breaker': {
            'triggered': cb_triggered,
            'reason': cb_reason,
            'params': cb.describe(),
        },
        'daily_stats': {
            'trades_today': stats.get('trades_today', 0),
            'consecutive_losses': stats.get('consecutive_losses', 0),
            'daily_pnl_pct': round(stats.get('daily_pnl_pct', 0.0) * 100, 2),
            'weekly_pnl_pct': round(stats.get('weekly_pnl_pct', 0.0) * 100, 2),
            'open_positions': int(open_positions),
        },
        'learner': learner_summary,
    }


@router.get("/decisions")
async def get_decisions(limit: int = 50):
    """Historial de decisiones autónomas del MetaEvaluador."""
    try:
        decisions = await db.get_autonomous_decisions(limit=limit)
        # Serializar para JSON (timestamps, Decimal, etc.)
        for d in decisions:
            if d.get('created_at'):
                d['created_at'] = d['created_at'].isoformat()
            if d.get('meta_score') is not None:
                d['meta_score'] = float(d['meta_score'])
            if d.get('confidence') is not None:
                d['confidence'] = float(d['confidence'])
            if d.get('trade_pnl') is not None:
                d['trade_pnl'] = float(d['trade_pnl'])
        return {'decisions': decisions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/toggle")
async def toggle_autonomous_mode(enable: bool):
    """
    Activa o desactiva el modo autónomo en tiempo de ejecución.

    Escribe en runtime_state.json — ambos procesos (dashboard + engine)
    leen desde ahí, así el toggle funciona sin reiniciar ninguno.
    """
    set_autonomous(enable)
    if enable:
        _log("🤖 [AUTONOMÍA] ══════════════════════════════════════")
        _log("🤖 [AUTONOMÍA] MODO AUTÓNOMO ACTIVADO por el operador")
        _log("🤖 [AUTONOMÍA] MetaEvaluador tomará decisiones automáticamente")
        _log("🤖 [AUTONOMÍA] ══════════════════════════════════════")
    else:
        _log("🖐 [AUTONOMÍA] ══════════════════════════════════════")
        _log("🖐 [AUTONOMÍA] MODO MANUAL ACTIVADO por el operador")
        _log("🖐 [AUTONOMÍA] Aprobación humana requerida para cada señal")
        _log("🖐 [AUTONOMÍA] ══════════════════════════════════════")
    return {
        'success': True,
        'autonomous_mode': enable,
        'message': f'Modo autónomo {"ACTIVADO" if enable else "DESACTIVADO"}',
    }


@router.post("/reset_cb")
async def reset_cb():
    """
    Reinicia los contadores del Circuit Breaker manualmente.

    No borra datos de la BD — marca un timestamp de reset en runtime_state.json.
    Los contadores (trades hoy, PnL día, pérdidas consecutivas) solo cuentan
    trades posteriores a este momento.
    """
    reset_at = reset_circuit_breaker()
    _log("🔄 [CIRCUIT BREAKER] ════════════════════════════════")
    _log("🔄 [CIRCUIT BREAKER] CONTADORES REINICIADOS por el operador")
    _log(f"🔄 [CIRCUIT BREAKER] Trades hoy, PnL día y racha de pérdidas → 0")
    _log(f"🔄 [CIRCUIT BREAKER] Reset desde: {reset_at}")
    _log("🔄 [CIRCUIT BREAKER] ════════════════════════════════")
    return {
        'success': True,
        'reset_at': reset_at,
        'message': 'Contadores del Circuit Breaker reiniciados.',
    }
