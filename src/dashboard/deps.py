"""
SysMho — Dependencias del Dashboard.

Centraliza las instancias globales de la base de datos y ejecutores
para evitar importaciones circulares en los routers de FastAPI.
"""

import time

from src.database.repository import DatabaseRepository
from src.executor.trader import TradeExecutor
from src.risk.manager import RiskManager
from src.executor.monitor import PositionMonitor
from src.paths import BRAIN_LOG


# Instancias globales compartidas
db = DatabaseRepository()
trader = TradeExecutor(db=db)
risk = RiskManager(db=db)
monitor = PositionMonitor(db=db, trader=trader)


def log_tactico(message: str) -> None:
    """Escribe un mensaje de mando en el log neuronal."""
    timestamp = time.strftime("%H:%M:%S")
    full_msg = f"[{timestamp}] [MANDO] {message}\n"
    try:
        with open(BRAIN_LOG, "a", encoding='utf-8') as f:
            f.write(full_msg)
            f.flush()
    except Exception as e:
        print(f"Error escribiendo log táctico: {e}")
