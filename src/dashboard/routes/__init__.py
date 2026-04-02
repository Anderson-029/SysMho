"""
SysMho — Definición del paquete de Rutas.
"""

from src.dashboard.routes.autonomous import router as autonomous_router
from src.dashboard.routes.market import router as market_router
from src.dashboard.routes.signals import router as signals_router
from src.dashboard.routes.positions import router as positions_router
from src.dashboard.routes.portfolio import router as portfolio_router
from src.dashboard.routes.system import router as system_router
from src.dashboard.routes.testing import router as testing_router

__all__ = [
    'autonomous_router',
    'market_router',
    'signals_router',
    'positions_router',
    'portfolio_router',
    'system_router',
    'testing_router'
]
