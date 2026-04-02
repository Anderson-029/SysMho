"""
SysMho — Rutas de Señales de IA y Autorización.
"""

from fastapi import APIRouter, HTTPException

from src.dashboard.deps import db, log_tactico

router = APIRouter(prefix="/api", tags=["Signals"])

@router.get("/pending_signals")
async def get_pending_signals():
    """Lista señales pendientes ordenadas: BOUNTY primero, luego REGULAR por score."""
    query = '''
        SELECT id, symbol, side, quantity, entry_price, stop_loss,
               take_profit, risk_score, invested_usdt, win_probability,
               loss_probability, potential_profit_usdt, potential_loss_usdt,
               created_at, signal_type, trend_5m, trend_1h, trend_4h,
               alert_category, score
        FROM pending_approvals
        WHERE status = 'PENDING'
        ORDER BY
            CASE alert_category WHEN 'BOUNTY' THEN 0 ELSE 1 END,
            score DESC,
            created_at DESC
    '''
    async with db.pool.acquire() as conn:
        records = await conn.fetch(query)

    result = []
    for r in records:
        row = dict(r)
        if row.get('created_at'):
            row['created_at'] = row['created_at'].isoformat()
        result.append(row)
    return result

@router.post("/signals/{id}/approve")
async def approve_signal(id: int):
    """Aprueba una señal pendiente."""
    query = '''
        UPDATE pending_approvals 
        SET status = 'APPROVED', resolved_at = NOW() 
        WHERE id = $1 AND status = 'PENDING' 
        RETURNING symbol, side
    '''
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(query, id)
        
    if not row:
        raise HTTPException(
            status_code=400, detail="Señal ya procesada o no válida."
        )
        
    log_tactico(
        f"✅ Autorizado: Orden de {row['side']} para {row['symbol']} aprobada."
    )
    return {"status": "ok", "detail": "Aprobada"}

@router.post("/signals/{id}/reject")
async def reject_signal(id: int):
    """Rechaza una señal pendiente."""
    query = '''
        UPDATE pending_approvals 
        SET status = 'REJECTED', resolved_at = NOW() 
        WHERE id = $1 AND status = 'PENDING' 
        RETURNING symbol, side
    '''
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(query, id)
        
    if not row:
        raise HTTPException(
            status_code=400, detail="Señal ya procesada o no válida."
        )
        
    log_tactico(
        f"❌ Rechazado: Señal de {row['side']} para {row['symbol']} denegada."
    )
    return {"status": "ok", "detail": "Rechazada"}

@router.post("/signals/dismiss_all")
async def dismiss_all_signals():
    """Limpia visualmente todas las señales pendientes sin afectar el entrenamiento."""
    query = '''
        UPDATE pending_approvals 
        SET status = 'DISMISSED', resolved_at = NOW() 
        WHERE status = 'PENDING'
    '''
    async with db.pool.acquire() as conn:
        await conn.execute(query)
        
    log_tactico("🧹 HUD: Panel de Auditoría limpiado por el Operador.")
    return {"status": "ok", "detail": "Panel limpiado"}

@router.get("/authorized_history")
async def get_authorized_history():
    """Historial de señales procesadas recientemente."""
    query = '''
        SELECT * FROM pending_approvals 
        WHERE status IN ('APPROVED', 'EXECUTED', 'FAILED', 'REJECTED') 
        ORDER BY resolved_at DESC LIMIT 10
    '''
    async with db.pool.acquire() as conn:
        rows = await conn.fetch(query)
        history = []
        for r in rows:
            signal = dict(r)
            if signal['resolved_at']:
                signal['resolved_at'] = signal['resolved_at'].isoformat()
            if signal['created_at']:
                signal['created_at'] = signal['created_at'].isoformat()
            history.append(signal)
        return history
