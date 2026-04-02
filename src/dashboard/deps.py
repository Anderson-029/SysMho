"""
SysMho — Dependencias del Dashboard.

Centraliza las instancias globales de la base de datos y ejecutores
para evitar importaciones circulares en los routers de FastAPI.
"""

import os
import time

from src.database.repository import DatabaseRepository
from src.executor.trader import TradeExecutor
from src.risk.manager import RiskManager
from src.executor.monitor import PositionMonitor


# Instancias globales compartidas
db = DatabaseRepository()
trader = TradeExecutor(db=db)
risk = RiskManager(db=db)
monitor = PositionMonitor(db=db, trader=trader)


def log_tactico(message: str) -> None:
    """Escribe un mensaje de mando en el log neuronal."""
    log_file = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
        "sysmho_brain.log"
    )
    timestamp = time.strftime("%H:%M:%S")
    full_msg = f"[{timestamp}] [MANDO] {message}\n"
    try:
        with open(log_file, "a", encoding='utf-8') as f:
            f.write(full_msg)
            f.flush()
    except Exception as e:
        print(f"Error escribiendo log táctico: {e}")
