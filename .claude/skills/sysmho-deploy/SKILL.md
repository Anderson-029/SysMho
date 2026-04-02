---
name: sysmho-deploy
description: Reinicia SysMho de forma controlada — verifica posiciones, para procesos, aplica migraciones pendientes y arranca en orden
user-invocable: true
allowed-tools: Bash, Read
---

Orquesta el reinicio controlado y seguro de SysMho.

## Paso 1 — Verificar posiciones abiertas

```bash
cd "/home/anderson/Documentos/programas personales/SysMho"
source venv/bin/activate && PYTHONPATH=$(pwd) python3 -c "
import asyncio, asyncpg
async def main():
    try:
        conn = await asyncpg.connect(host='localhost', port=5432, user='postgres', password='ander123', database='sysmho')
        count = await conn.fetchval('SELECT COUNT(*) FROM positions')
        print(f'Posiciones abiertas: {count}')
        if count > 0:
            rows = await conn.fetch('SELECT symbol, side, pnl_unrealized FROM positions')
            for r in rows:
                print(f'  ⚠️  {r[\"symbol\"]} {r[\"side\"]} PnL={r[\"pnl_unrealized\"]:.2f}')
        await conn.close()
    except Exception as e:
        print(f'BD no disponible: {e}')
asyncio.run(main())
" 2>&1
```

Si hay posiciones abiertas, **advertir claramente** que apagarlas las dejará sin vigilancia de SL/TP. Pedir confirmación explícita antes de continuar.

## Paso 2 — Detener procesos actuales

```bash
pkill -f "uvicorn src.dashboard.api" 2>/dev/null && echo "Dashboard detenido" || echo "Dashboard ya estaba detenido"
sleep 1
pkill -f "python.*src.main" 2>/dev/null && echo "Motor detenido" || echo "Motor ya estaba detenido"
sleep 2
```

## Paso 3 — Verificar migraciones pendientes

Lista los archivos SQL en `src/database/` y compara con las tablas actuales en la BD. Si hay migraciones no aplicadas, advertir y preguntar si aplicarlas antes de arrancar.

## Paso 4 — Limpiar log neuronal (opcional)

Preguntar si quiere limpiar el log antes de arrancar:
```bash
> "/home/anderson/Documentos/programas personales/SysMho/src/sysmho_brain.log"
echo "Log limpiado"
```

## Paso 5 — Arrancar en orden correcto

```bash
cd "/home/anderson/Documentos/programas personales/SysMho"
source venv/bin/activate
export PYTHONPATH=$(pwd)

# Dashboard primero
nohup uvicorn src.dashboard.api:app --host 0.0.0.0 --port 8000 > /dev/null 2>&1 &
sleep 3
echo "Dashboard: $(curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/health 2>/dev/null || echo 'verificar manualmente')"

# Motor después
nohup python -m src.main > /dev/null 2>&1 &
sleep 2
```

## Paso 6 — Verificar arranque

```bash
ps aux | grep -E "uvicorn|src\.main" | grep -v grep
```

```bash
tail -20 "/home/anderson/Documentos/programas personales/SysMho/src/sysmho_brain.log" 2>/dev/null
```

## Reporte final

```
DEPLOY SYSMHO v15.2.0 — [FECHA HORA]
─────────────────────────────────────
Posiciones preservadas: N
Dashboard: ✅ corriendo (puerto 8000)
Motor: ✅ corriendo
Gap Filler: iniciando (ver logs)
URL: http://localhost:8000
```
