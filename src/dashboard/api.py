"""
SysMho — Command Center API.

Punto de entrada principal para el Dashboard (Backend).
Monta los sub-routers divididos lógicamente y gestiona recursos globales.
"""

from dotenv import load_dotenv
load_dotenv()

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from src.dashboard.deps import db, trader
from src.dashboard.routes import (
    autonomous_router,
    market_router,
    positions_router,
    portfolio_router,
    signals_router,
    system_router,
    testing_router
)

# Clave de API para el dashboard (requerida en el header X-API-Key)
DASHBOARD_API_KEY = os.environ.get("DASHBOARD_API_KEY", "")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestiona el ciclo de vida de la aplicación (startup / shutdown)."""
    await db.connect()
    yield
    await db.close()
    await trader.close_connection()


app = FastAPI(title="SysMho ComCenter API", lifespan=lifespan)


@app.middleware("http")
async def api_key_middleware(request: Request, call_next):
    """Rechaza peticiones sin el header X-API-Key correcto."""
    # Rutas públicas: el propio index y assets estáticos
    if request.url.path == "/" or request.url.path.startswith("/assets"):
        return await call_next(request)

    if DASHBOARD_API_KEY:
        api_key = request.headers.get("X-API-Key", "")
        if api_key != DASHBOARD_API_KEY:
            return JSONResponse(
                status_code=403,
                content={"detail": "API Key inválida o ausente."}
            )

    return await call_next(request)


# Montar recursos estáticos (Frontend)
static_dir = os.path.join(os.path.dirname(__file__), "static")
assets_dir = os.path.join(static_dir, "assets")
app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

# Montar Routers Modulares
app.include_router(autonomous_router)
app.include_router(market_router)
app.include_router(signals_router)
app.include_router(positions_router)
app.include_router(portfolio_router)
app.include_router(system_router)
app.include_router(testing_router)


@app.get("/")
async def serve_dashboard():
    """Sirve la interfaz gráfica principal (index.html)."""
    return FileResponse(os.path.join(static_dir, "index.html"))
