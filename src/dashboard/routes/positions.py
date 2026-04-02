"""
SysMho — Rutas de Posiciones de Trading.
"""

from fastapi import APIRouter, HTTPException

from src.dashboard.deps import db, monitor, log_tactico

router = APIRouter(prefix="/api/positions", tags=["Positions"])

@router.get("")
async def get_positions():
    """Obtiene posiciones abiertas activas."""
    query = "SELECT * FROM positions ORDER BY opened_at DESC"
    async with db.pool.acquire() as conn:
        rows = await conn.fetch(query)
        positions = []
        for r in rows:
            pos = dict(r)
            if pos['opened_at']:
                pos['opened_at'] = pos['opened_at'].isoformat()
            if pos['updated_at']:
                pos['updated_at'] = pos['updated_at'].isoformat()
            positions.append(pos)
        return positions

@router.post("/{symbol_encoded}/close")
async def close_position(symbol_encoded: str):
    """Cierra manual y forzosamente una posición activa."""
    symbol = symbol_encoded.replace("-", "/")
    success = await monitor.manual_close_position(symbol)
    
    if success:
        log_tactico(
            f"⚔️ Orden de Salida: Posición {symbol} cerrada manualmente."
        )
        return {
            "status": "success", 
            "message": f"Posición {symbol} cerrada."
        }
    else:
        raise HTTPException(
            status_code=404, detail="Posición no encontrada."
        )
