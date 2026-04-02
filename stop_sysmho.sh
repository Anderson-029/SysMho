#!/bin/bash

# Limpiar pantalla
clear
echo -e "\e[31m=================================================\e[0m"
echo -e "\e[31m APAGADO DE SYSMHO V15.2.0...\e[0m"
echo -e "\e[31m=================================================\e[0m"

# Rutas absolutas para evitar errores de contexto
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

sleep 1

# Verificar posiciones abiertas antes de apagar
echo -e "[🔍] \e[33mVerificando posiciones abiertas...\e[0m"
OPEN_POSITIONS=$(source venv/bin/activate 2>/dev/null && python -c "
import asyncio, asyncpg, os
from dotenv import load_dotenv
load_dotenv()
async def count():
    try:
        conn = await asyncpg.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            port=int(os.getenv('DB_PORT', '5432')),
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD', 'postgres'),
            database=os.getenv('DB_NAME', 'sysmho')
        )
        c = await conn.fetchval('SELECT COUNT(*) FROM positions')
        await conn.close()
        print(int(c))
    except Exception:
        print(0)
asyncio.run(count())
" 2>/dev/null)

if [ -n "$OPEN_POSITIONS" ] && [ "$OPEN_POSITIONS" -gt "0" ] 2>/dev/null; then
    echo -e "\e[31m⚠️  ADVERTENCIA: Hay $OPEN_POSITIONS posición(es) abierta(s) en la BD.\e[0m"
    echo -e "\e[33m   Apagar ahora dejará esas posiciones SIN vigilancia de SL/TP.\e[0m"
    read -r -p "$(echo -e '\e[33m¿Continuar de todas formas? [s/N]: \e[0m')" confirm
    if [[ "$confirm" != "s" && "$confirm" != "S" ]]; then
        echo -e "\e[32mApagado cancelado. SysMho sigue activo.\e[0m"
        exit 0
    fi
else
    echo -e "\e[32m   Sin posiciones abiertas. Apagado seguro.\e[0m"
fi

echo -e "[📡] \e[33mDesconectando Panel de Control Web C2...\e[0m"
pkill -f "uvicorn src.dashboard.api" || echo -e "\e[90m(API ya estaba detenida)\e[0m"
sleep 1

echo -e "[🧠] \e[35mApagando Motor Cuantitativo y de IA...\e[0m"
pkill -f "python.*src.main" || echo -e "\e[90m(Motor ya estaba detenido)\e[0m"
sleep 1

echo -e "\e[32m✅ SysMho en reposo total y red neuronal desactivada.\e[0m"
