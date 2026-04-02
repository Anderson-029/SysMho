"""
SysMho — Rutas del Mercado.
"""

from fastapi import APIRouter

from src.dashboard.deps import db

router = APIRouter(prefix="/api", tags=["Market"])

@router.get("/market_data/{symbol_encoded}")
async def get_market_data(
    symbol_encoded: str, timeframe: str = '5m', limit: int = 288
):
    """Obtiene datos de mercado para Lightweight Charts."""
    symbol = symbol_encoded.replace("-", "/")
    query = '''
        SELECT * FROM (
            SELECT open_time, open, high, low, close, volume 
            FROM market_data 
            WHERE symbol = $1 AND timeframe = $2
            ORDER BY open_time DESC 
            LIMIT $3
        ) sub
        ORDER BY open_time ASC
    '''
    async with db.pool.acquire() as conn:
        records = await conn.fetch(query, symbol, timeframe, limit)
        
    formatted = []
    for row in records:
        formatted.append({
            "time": int(row['open_time'].timestamp()),
            "open": float(row['open']),
            "high": float(row['high']),
            "low": float(row['low']),
            "close": float(row['close']),
            "volume": float(row['volume'])
        })
        
    return formatted
