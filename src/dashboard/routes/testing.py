"""
SysMho — Rutas de Simulaciones / Testing.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.dashboard.deps import db, trader, risk

router = APIRouter(prefix="/api/test", tags=["Testing"])

class TestSignal(BaseModel):
    symbol: str
    side: str

@router.post("/inject_signal")
async def inject_test_signal(test: TestSignal):
    """
    Inyecta una señal al pool PENDING para validación desde el frontend.
    Simula el dictamen de la Inteligencia Artificial.
    """
    query_price = '''
        SELECT close, atr_14 FROM market_data 
        WHERE symbol = $1 ORDER BY open_time DESC LIMIT 1
    '''
    async with db.pool.acquire() as conn:
        price_row = await conn.fetchrow(query_price, test.symbol)
    
    if not price_row:
        raise HTTPException(
            status_code=400, 
            detail=f"No hay datos de mercado recientes para {test.symbol}."
        )
    
    side_str = test.side.upper()
    signal_data = {
        'signal_int': 1 if side_str == 'BUY' else -1,
        'signal_str': side_str,
        'confidence': 0.85,
        'raw_probs': [0.05, 0.10, 0.85] if side_str == 'BUY' else [0.85, 0.10, 0.05]
    }
    
    current_market = {
        'close': float(price_row['close']),
        'atr_14': float(price_row['atr_14'] or 5.0)
    }
    
    balance = await trader.get_portfolio_balance()
    dictamen = await risk.evaluate_signal(
        test.symbol, signal_data, current_market, balance
    )
    
    if not dictamen.get('approved'):
        return {
            "status": "rejected_by_risk", 
            "reason": dictamen.get('reason', 'Sin razón definida')
        }
        
    query_insert = '''
        INSERT INTO pending_approvals (
            symbol, side, quantity, entry_price, stop_loss, take_profit, 
            risk_score, invested_usdt, win_probability, loss_probability, 
            potential_profit_usdt, potential_loss_usdt, exposure_warning, 
            signal_type, trend_5m, trend_1h, trend_4h
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, 
            $14, $15, $16, $17
        ) RETURNING id
    '''
    
    try:
        async with db.pool.acquire() as conn:
            pending_id = await conn.fetchval(
                query_insert, test.symbol, side_str, 
                dictamen['quantity'], current_market['close'], 
                dictamen['stop_loss'], dictamen['take_profit'], 
                0.85, dictamen['invested_usdt'], 
                dictamen['win_probability'], dictamen['loss_probability'],
                dictamen['potential_profit_usdt'], 
                dictamen['potential_loss_usdt'],
                dictamen.get('exposure_warning', False), 'EXPLORACIÓN',
                'UP', 'NEUTRAL', 'DOWN'
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error BD: {e}")
    
    return {"status": "injected", "pending_id": pending_id}
