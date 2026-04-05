"""
SysMho — Rutas del Sistema y Telemetría.
"""

import os
import time
from fastapi import APIRouter

from src.dashboard.deps import trader, db
from src.runtime_config import get_last_scan_at

router = APIRouter(prefix="/api", tags=["System"])

@router.get("/system/status")
async def get_system_status():
    """Reporta el estado de salud en tiempo real del puente C2 con Binance."""
    # Forzamos una verificación real en cada pull del dashboard. 
    # CCXT.fetch_balance() pesa ~1 rate limit (ínfimo para 3s - 10s de intervalo)
    await trader.check_api_link()
    status = trader.api_status
        
    return {
        "api_link": status,
        "last_check": time.time()
    }

@router.get("/system/last_scan")
async def get_last_scan():
    """
    Retorna el timestamp del último scan REGULAR ejecutado por el motor de IA.
    El frontend lo usa para calcular el cronómetro real del próximo scan.

    Fuente primaria: runtime_state.json (se escribe aunque todos queden en WAIT).
    Fallback: MAX(created_at) de pending_approvals (solo hay registro si hubo señales).
    """
    from datetime import datetime, timezone

    # 1. Fuente primaria: runtime_state.json
    last_scan_iso = get_last_scan_at()
    if last_scan_iso:
        try:
            dt = datetime.fromisoformat(last_scan_iso)
            ts = dt.timestamp()
            return {
                "last_scan_ts": ts,
                "next_scan_in": max(0, 300 - (time.time() - ts)),
            }
        except (ValueError, TypeError):
            pass

    # 2. Fallback: DB (cuando el motor aún no ha corrido desde este arranque)
    query = '''
        SELECT MAX(created_at) AS last_scan
        FROM pending_approvals
        WHERE alert_category = 'REGULAR'
          AND created_at > NOW() - INTERVAL '24 hours'
    '''
    try:
        async with db.pool.acquire() as conn:
            row = await conn.fetchrow(query)
        last_scan = row['last_scan']
        if last_scan:
            return {
                "last_scan_ts": last_scan.timestamp(),
                "next_scan_in": max(0, 300 - (time.time() - last_scan.timestamp())),
            }
        return {"last_scan_ts": None, "next_scan_in": None}
    except Exception as e:
        return {"last_scan_ts": None, "next_scan_in": None, "error": str(e)}


@router.get("/data/freshness")
async def get_data_freshness():
    """
    Verifica la frescura de los datos de mercado en tiempo real.
    Devuelve la antigüedad de la última vela 5m recibida por símbolo
    y un estado global: FRESH (<2min), DELAYED (2-10min), STALE (>10min).
    """
    query = '''
        SELECT symbol, MAX(open_time) AS last_candle
        FROM market_data
        WHERE timeframe = '5m'
        GROUP BY symbol
        ORDER BY symbol
    '''
    now = time.time()
    symbols_status = []
    max_age_seconds = 0

    try:
        async with db.pool.acquire() as conn:
            records = await conn.fetch(query)

        for row in records:
            last_ts = row['last_candle'].timestamp()
            age_s   = now - last_ts
            max_age_seconds = max(max_age_seconds, age_s)
            symbols_status.append({
                "symbol":     row['symbol'],
                "last_candle": row['last_candle'].isoformat(),
                "age_seconds": round(age_s),
            })

        # Las velas de 5m pueden tener hasta 330s (5min30s) de antigüedad de forma normal.
        # Solo es DELAYED si se perdió una vela completa (>5min30s), STALE si son varias.
        if max_age_seconds < 330:
            status = "FRESH"
        elif max_age_seconds < 900:
            status = "DELAYED"
        else:
            status = "STALE"

        return {
            "status":          status,
            "max_age_seconds": round(max_age_seconds),
            "symbols":         symbols_status,
            "checked_at":      now,
        }
    except Exception as e:
        return {"status": "ERROR", "detail": str(e), "checked_at": now}


@router.get("/db/status")
async def get_db_status():
    """Verifica la conexión en tiempo real con PostgreSQL."""
    try:
        async with db.pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return {"db_link": "ACTIVE", "last_check": time.time()}
    except Exception:
        return {"db_link": "DISCONNECTED", "last_check": time.time()}


@router.get("/system/sync_status")
async def get_sync_status():
    """Estado del relleno automático de datos históricos (Gap Filler)."""
    from src.runtime_config import get_sync_status
    return get_sync_status()


@router.get("/logs")
async def get_logs(limit: int = 500):
    """Lee el pensamiento táctico y neuronal en vivo."""
    from src.paths import BRAIN_LOG
    
    if not os.path.exists(BRAIN_LOG):
        return {"logs": ["🧠 SysMho: Dormido. Esperando ignición..."]}
        
    try:
        with open(BRAIN_LOG, "r", encoding="utf-8") as f:
            lines = f.readlines()
            return {"logs": [line.strip() for line in lines[-limit:]]}
    except Exception as e:
        return {"logs": [f"Error leyendo la telemetría neuronal: {e}"]}
