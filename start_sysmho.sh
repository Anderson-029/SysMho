#!/bin/bash

# Limpiar pantalla para presentación
clear

echo -e "\e[36m=================================================\e[0m"
echo -e "\e[32m SYSMHO (V15.2.0) - Sistema SysMho Integrado \e[0m"
echo -e "\e[36m=================================================\e[0m"

# Rutas absolutas para evitar errores de contexto
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# Purgamos la memoria de corto plazo de la terminal neuronal
> src/sysmho_brain.log

echo -e "\n[⚡] \e[33mDespertando red neuronal...\e[0m"
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
else
    echo -e "\e[31mError: No se encontró el entorno virtual en 'venv'. Por favor, créalo primero.\e[0m"
    exit 1
fi
sleep 1.5

echo -e "[📡] \e[34mEstableciendo enlace C2 (Command & Control) en puerto 8000...\e[0m"
uvicorn src.dashboard.api:app --host 0.0.0.0 --port 8000 > /dev/null 2>&1 &
sleep 2

echo -e "[🧠] \e[35mIniciando motor XGBoost, Autonomía, Circuit Breaker y Gap Filler...\e[0m"
export PYTHONPATH=$PROJECT_DIR
nohup python -m src.main > /dev/null 2>&1 &
sleep 2

echo -e "[🌐] \e[36mDesplegando Interfaz Táctica Automática...\e[0m"
if command -v xdg-open > /dev/null; then
    xdg-open http://localhost:8000 > /dev/null 2>&1
elif command -v sensible-browser > /dev/null; then
    sensible-browser http://localhost:8000 > /dev/null 2>&1
else
    python -m webbrowser "http://localhost:8000" > /dev/null 2>&1
fi
sleep 1

echo -e "\n\e[32m✅ ¡SysMho 100% Operativo! cargado y esperando confirmación visual.\e[0m"
echo -e "\e[90m(Para detener a SysMho, ejecuta: ./stop_sysmho.sh)\e[0m\n"
