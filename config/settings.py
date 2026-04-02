"""
SysMho — Configuración Centralizada.

Carga las variables de entorno desde el archivo .env y expone
las constantes de configuración para todo el sistema.
"""

import os
from dotenv import load_dotenv

# Carga las variables del .env
load_dotenv()

# ============================================================
# Binance Configuration
# ============================================================
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
BINANCE_SECRET_KEY = os.getenv("BINANCE_SECRET_KEY")
BINANCE_TESTNET = os.getenv("BINANCE_TESTNET", "True") == "True"

# ============================================================
# Database Configuration
# ============================================================
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
DB_NAME = os.getenv("DB_NAME", "sysmho")

# DSN for asyncpg
DATABASE_URL = (
    f"postgresql://{DB_USER}:{DB_PASSWORD}"
    f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

# ============================================================
# Validación de Arranque
# ============================================================
if not BINANCE_API_KEY or not BINANCE_SECRET_KEY:
    raise ValueError(
        "\n🚨 [CONFIG] BINANCE_API_KEY y BINANCE_SECRET_KEY son obligatorias.\n"
        "   Verifica que tu archivo .env exista y contenga ambas claves."
    )
