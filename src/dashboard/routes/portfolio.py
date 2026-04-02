"""
SysMho — Rutas de Portafolio y Finanzas.
"""

import time
from datetime import date, datetime, timezone

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.dashboard.deps import db, trader, log_tactico
from src.constants import BINANCE_FUTURES_TAKER_FEE

router = APIRouter(prefix="/api", tags=["Portfolio"])

# Caché simple en memoria para evitar colapsar la API gratis
CURRENCY_RATES = {
    "COP": 3950.0,
    "EUR": 0.92,
    "last_update": 0
}

async def get_exchange_rates() -> dict:
    global CURRENCY_RATES
    now = time.time()
    if now - CURRENCY_RATES["last_update"] > 3600:
        try:
            url = "https://api.exchangerate-api.com/v4/latest/USD"
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(url)
            if response.status_code == 200:
                data = response.json()
                CURRENCY_RATES["COP"] = data["rates"].get("COP", 3950.0)
                CURRENCY_RATES["EUR"] = data["rates"].get("EUR", 0.92)
                CURRENCY_RATES["last_update"] = now
        except Exception as e:
            print(f"⚠️ [DIVISAS] Error actualizando tasas: {e}")
    return CURRENCY_RATES

class CapitalAdjustment(BaseModel):
    capital_cop: float

@router.get("/balance")
async def get_balance():
    """Consulta el balance operativo."""
    try:
        balance = await trader.get_portfolio_balance()
        return {"balance": balance}
    except Exception as e:
        return {"balance": 0.0, "error": str(e)}

@router.get("/stats")
async def get_stats():
    """KPIs macro financieros para el Dashboard."""
    from src.runtime_config import get_pnl_reset_at
    pnl_reset_at = get_pnl_reset_at()

    # Límite de tiempo para el PnL diario: medianoche de hoy o el último reset manual
    today_start = datetime.combine(date.today(), datetime.min.time()).replace(tzinfo=timezone.utc)
    if pnl_reset_at:
        try:
            reset_dt = datetime.fromisoformat(pnl_reset_at)
            effective_start = max(today_start, reset_dt)
        except (ValueError, TypeError):
            effective_start = today_start
    else:
        effective_start = today_start

    query_closed = '''
        SELECT COUNT(*) as total, SUM(pnl) as pnl_realizado,
               COUNT(*) FILTER (WHERE pnl > 0) as winners
        FROM trades WHERE status = 'CLOSED'
    '''
    query_daily_pnl = '''
        SELECT COALESCE(SUM(pnl), 0) as pnl_diario
        FROM trades
        WHERE status = 'CLOSED'
          AND executed_at >= $1
    '''
    query_active = '''
        SELECT COUNT(*) as count, COALESCE(SUM(invested_usdt), 0) as margin,
               COALESCE(SUM(pnl_unrealized), 0) as floating_pnl,
               COALESCE(SUM(quantity * current_price), 0) as open_notional
        FROM positions
    '''
    query_portfolio = '''
        SELECT total_balance, available_balance, in_positions
        FROM portfolio ORDER BY recorded_at DESC LIMIT 1
    '''

    async with db.pool.acquire() as conn:
        closed = await conn.fetchrow(query_closed)
        daily = await conn.fetchrow(query_daily_pnl, effective_start)
        active = await conn.fetchrow(query_active)
        portfolio = await conn.fetchrow(query_portfolio)
        
    total_trades = closed['total'] or 0
    win_rate = (
        (closed['winners'] / total_trades * 100) if total_trades > 0 else 0
    )
    pnl_realizado = float(closed['pnl_realizado'] or 0.0)
    
    active_count = active['count'] or 0
    rates = await get_exchange_rates()

    try:
        binance_data = await trader.exchange.fetch_balance()
        # CCXT Normalized Keys
        total_binance = float(binance_data['total'].get('USDT', 0.0))
        available = float(binance_data['free'].get('USDT', 0.0))
        margin_active = float(binance_data['used'].get('USDT', 0.0))
        
        # Intentar extraer PnL Flotante del raw JSON, si falla usar el de CCXT o DB local
        info = binance_data.get('info', {})
        if isinstance(info, dict):
            floating_pnl = float(info.get('totalUnrealizedProfit', active['floating_pnl'] or 0.0))
            current_total_balance = float(info.get('totalMarginBalance', total_binance + floating_pnl))
        else:
            floating_pnl = float(active['floating_pnl'] or 0.0)
            current_total_balance = total_binance + floating_pnl
            
        binance_reserve = total_binance

    except Exception as e:
        print(f"❌ [API STATS] Error calculando balance: {e}")
        total_binance = 0.0
        margin_active = 0.0
        floating_pnl = 0.0
        available = 0.0
        current_total_balance = 0.0
        binance_reserve = 0.0

    # PnL diario neto = realizados hoy (ya con fees descontadas en monitor.py)
    #                 + flotante estimado neto (descontando fee de cierre si cerráramos ahora)
    pnl_diario_realizado = float(daily['pnl_diario'] if daily else 0.0)
    open_notional = float(active['open_notional'] or 0.0)
    estimated_close_fee = open_notional * BINANCE_FUTURES_TAKER_FEE
    floating_pnl_net = floating_pnl - estimated_close_fee
    pnl_diario = round(pnl_diario_realizado + floating_pnl_net, 2)

    return {
        "total_trades": total_trades,
        "win_rate": round(win_rate, 2),
        "pnl_realizado": round(pnl_realizado, 2),
        "margin_in_use": round(margin_active, 2),
        "floating_pnl": round(floating_pnl, 2),
        "active_trades": active_count,
        "pnl_diario": pnl_diario,
        "total_balance": round(current_total_balance, 2),
        "available_balance": round(available, 2),
        "binance_balance": round(binance_reserve, 2),
        "rates": {
            "COP": rates["COP"], "EUR": rates["EUR"], "USD": 1.0
        }
    }

@router.get("/trades/history")
async def get_trade_history():
    """Últimos trades cerrados."""
    query = "SELECT * FROM trades ORDER BY executed_at DESC LIMIT 10"
    async with db.pool.acquire() as conn:
        rows = await conn.fetch(query)
        history = []
        for r in rows:
            trade = dict(r)
            trade['executed_at'] = trade['executed_at'].isoformat()
            history.append(trade)
        return history

@router.post("/portfolio/transfer_to_reserve")
async def transfer_to_reserve():
    """Devuelve todo el capital operativo al fondo de reserva (0)."""
    query = '''
        UPDATE portfolio 
        SET total_balance = 0, available_balance = 0, 
            in_positions = 0, total_pnl = 0 
        WHERE id = (SELECT id FROM portfolio ORDER BY recorded_at DESC LIMIT 1)
    '''
    try:
        async with db.pool.acquire() as conn:
            await conn.execute(query)
        log_tactico(
            "🏦 Fondos reintegrados a la Reserva del Exchange. "
            "Capital reseteado a 0."
        )
        return {
            "status": "success", 
            "message": "Capital transferido a la reserva."
        }
    except Exception as e:
        log_tactico(f"❌ Error en transferencia a reserva: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/portfolio/reset_pnl")
async def reset_daily_pnl_endpoint():
    """Reinicia el contador de PnL diario (sin borrar trades reales)."""
    from src.runtime_config import reset_daily_pnl
    ts = reset_daily_pnl()
    log_tactico(f"🔄 PnL diario reiniciado manualmente. Nuevo punto de inicio: {ts}")
    return {"status": "success", "reset_at": ts}


@router.post("/portfolio/adjust_capital")
async def adjust_portfolio_capital(adj: CapitalAdjustment):
    """Ajusta el capital total partiendo de una cifra en COP."""
    rates = await get_exchange_rates()
    cop_rate = rates.get("COP", 3950.0)
    
    new_usdt = round(adj.capital_cop / cop_rate, 2)
    
    try:
        binance_data = await trader.exchange.fetch_balance()
        total_binance = float(binance_data['total'].get('USDT', 0.0))
        
        if new_usdt > total_binance:
            log_tactico(
                f"⚠️ ADVERTENCIA: Se solicitó {new_usdt} USDT pero solo hay "
                f"{total_binance} USDT en la reserva."
            )
            msg = (
                f"Inviabilidad Táctica: Capital ($USD {new_usdt}) "
                f"excede la Reserva ($USD {total_binance})."
            )
            raise HTTPException(status_code=400, detail=msg)
            
    except HTTPException:
        raise
    except Exception as e:
        log_tactico(f"❌ Error con Binance durante validación: {e}")
        log_tactico("⚠️ Validación deshabilitada por fallo de conexión.")

    query = '''
        UPDATE portfolio
        SET total_balance    = $1,
            available_balance = $1 - $2,
            total_pnl        = 0.0,
            in_positions     = $2
        WHERE id = (SELECT id FROM portfolio ORDER BY recorded_at DESC LIMIT 1)
    '''

    try:
        async with db.pool.acquire() as conn:
            # Leer capital actualmente en posiciones abiertas para no pisarlo
            current_in_positions = await conn.fetchval(
                "SELECT COALESCE(SUM(invested_usdt), 0.0) FROM positions"
            ) or 0.0
            await conn.execute(query, float(new_usdt), float(current_in_positions))
        log_tactico(
            f"💰 Ajuste: Capital Operativo cargado con {adj.capital_cop} "
            f"COP (~{new_usdt} USDT)."
        )
        return {"status": "success", "new_usdt": new_usdt}
    except Exception as e:
        log_tactico(f"❌ FALLO TÁCTICO al ajustar capital: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {e}")
