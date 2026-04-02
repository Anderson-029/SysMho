"""
SysMho — Configuración Global de Tests.

Provee fixtures compartidos para todos los módulos de prueba:
- db_pool: pool de conexiones a la BD real (para tests de integración)
"""

import os

import asyncpg
import pytest
from dotenv import load_dotenv

load_dotenv()

_DATABASE_URL = (
    f"postgresql://{os.getenv('DB_USER', 'postgres')}:"
    f"{os.getenv('DB_PASSWORD', 'postgres')}"
    f"@{os.getenv('DB_HOST', 'localhost')}:"
    f"{os.getenv('DB_PORT', '5432')}/"
    f"{os.getenv('DB_NAME', 'sysmho')}"
)


@pytest.fixture()
async def db_pool():
    """Pool de conexiones a la BD real. Requiere que PostgreSQL esté corriendo."""
    pool = await asyncpg.create_pool(_DATABASE_URL, min_size=1, max_size=3)
    yield pool
    await pool.close()
