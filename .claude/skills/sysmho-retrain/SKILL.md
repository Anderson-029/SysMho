---
name: sysmho-retrain
description: Orquesta el reentrenamiento seguro del modelo XGBoost de SysMho — verifica datos, limpia modelo viejo, reentrena y valida métricas
user-invocable: true
allowed-tools: Bash, Read
---

Ejecuta el reentrenamiento del modelo XGBoost de SysMho de forma segura y verificada.

## Paso 1 — Verificar volumen de datos disponible

```bash
cd "/home/anderson/Documentos/programas personales/SysMho"
source venv/bin/activate && PYTHONPATH=$(pwd) python3 -c "
import asyncio, asyncpg
async def main():
    conn = await asyncpg.connect(host='localhost', port=5432, user='postgres', password='ander123', database='sysmho')
    counts = await conn.fetch('''
        SELECT symbol, timeframe, COUNT(*) as candles,
               MIN(open_time) as desde, MAX(open_time) as hasta
        FROM market_data
        GROUP BY symbol, timeframe
        ORDER BY symbol, timeframe
    ''')
    print('Velas disponibles por símbolo/temporalidad:')
    for r in counts:
        print(f'  {r[\"symbol\"]} {r[\"timeframe\"]}: {r[\"candles\"]:,} velas ({r[\"desde\"].date()} → {r[\"hasta\"].date()})')
    await conn.close()
asyncio.run(main())
" 2>&1
```

Si algún símbolo tiene menos de 10,000 velas en 5m, advertir antes de continuar.

## Paso 2 — Verificar modelo actual

```bash
ls -lh "/home/anderson/Documentos/programas personales/SysMho/src/ai/models/"
```

Muestra el modelo actual y su fecha de modificación. Pregunta si confirma reemplazarlo.

## Paso 3 — Backup del modelo actual

```bash
cd "/home/anderson/Documentos/programas personales/SysMho/src/ai/models"
cp xgboost_v1.joblib "xgboost_v1_backup_$(date +%Y%m%d_%H%M).joblib" 2>/dev/null && echo "Backup creado" || echo "No había modelo previo"
```

## Paso 4 — Eliminar modelo viejo

```bash
rm -f "/home/anderson/Documentos/programas personales/SysMho/src/ai/models/xgboost_v1.joblib"
echo "Modelo anterior eliminado"
```

## Paso 5 — Reentrenar

Pregunta al usuario: ¿reentrenar con parámetros existentes o con nueva sintonía Optuna?

**Opción A — Rápido** (usa best_params.joblib existente, ~5-10 min):
```bash
cd "/home/anderson/Documentos/programas personales/SysMho"
source venv/bin/activate && PYTHONPATH=$(pwd) python -m src.ai.trainer --symbol ALL --timeframe 5m 2>&1
```

**Opción B — Completo** (nueva sintonía Bayesiana, ~30-60 min):
```bash
cd "/home/anderson/Documentos/programas personales/SysMho"
source venv/bin/activate && PYTHONPATH=$(pwd) python -m src.ai.trainer --symbol ALL --timeframe 5m --tune --trials 50 2>&1
```

## Paso 6 — Verificar resultado

```bash
ls -lh "/home/anderson/Documentos/programas personales/SysMho/src/ai/models/xgboost_v1.joblib"
```

Si el archivo existe y tiene tamaño > 0: reentrenamiento exitoso.

Muestra las métricas de rendimiento del nuevo modelo comparadas con las anteriores (Win Rate CV y Hold-out por activo).

## Paso 7 — Verificar que el sistema puede cargar el nuevo modelo

```bash
cd "/home/anderson/Documentos/programas personales/SysMho"
source venv/bin/activate && PYTHONPATH=$(pwd) python3 -c "
from src.ai.predictor import SignalPredictor
p = SignalPredictor()
print('✅ Modelo cargado correctamente')
print(f'Features: {len(p.model.feature_names_in_) if hasattr(p.model, \"feature_names_in_\") else \"N/A\"}')
" 2>&1
```

## Reporte final

```
REENTRENAMIENTO COMPLETADO
Modelo anterior: backup_FECHA.joblib
Modelo nuevo: xgboost_v1.joblib (X MB)
Duración: ~X minutos
Métricas promedio: WR CV X% | Hold-out X%
Estado: ✅ Listo para producción
```
