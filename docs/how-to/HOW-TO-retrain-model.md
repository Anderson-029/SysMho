# Cómo Reentrenar el Modelo XGBoost

## Cuándo usar esta guía
- Cada 1-2 semanas (mantenimiento rutinario)
- Después de ejecutar el Gap Filler para recopilar datos nuevos
- Si el accuracy observable en producción baja de 90%
- Si modificaste `MODEL_FEATURES` en `src/constants.py` (obligatorio por model-guard rule)
- Después de un período sin operar (ej: vacaciones)

## Requisitos Previos
- PostgreSQL corriendo con datos en `market_data`
- ≥25,920 velas 5m por símbolo en los últimos 3 meses
- Engine detenido (evita conflictos al escribir el archivo `.joblib`)

---

## Paso 1: Verificar datos suficientes

```sql
-- Ejecutar con: uv run python -c "..." o psql
SELECT symbol, timeframe, COUNT(*) as total,
       MIN(open_time) as first, MAX(open_time) as last
FROM market_data
WHERE open_time >= NOW() - INTERVAL '3 months'
GROUP BY symbol, timeframe
ORDER BY symbol, timeframe;
```

Esperado: cada fila símbolo/5m debe tener ≥20,000 velas.
Si algún símbolo tiene vacíos, ejecuta el Gap Filler primero:

```bash
uv run python -c "
from dotenv import load_dotenv; load_dotenv()
import asyncio
from src.collector.gap_filler import GapFiller
from src.database.repository import DatabaseRepository
from src.constants import SYMBOLS

async def main():
    db = DatabaseRepository()
    await db.connect()
    await GapFiller(db).fill_all_gaps(SYMBOLS)
    await db.close()

asyncio.run(main())
"
```

---

## Paso 2: Hacer backup del modelo actual

```bash
cp src/ai/models/xgboost_v1_1.joblib \
   src/ai/models/xgboost_v1_1_backup_$(date +%Y%m%d).joblib

echo "Backup creado: xgboost_v1_1_backup_$(date +%Y%m%d).joblib"
```

---

## Paso 3: Borrar modelo viejo (requerido por model-guard rule)

```bash
rm src/ai/models/xgboost_v1_1.joblib
```

> La regla model-guard (`.claude/rules/model-guard.md`) bloquea commits si existe un `.joblib` viejo cuando `MODEL_FEATURES` cambia. Borrarlo explícitamente es el enfoque limpio.

---

## Paso 4a: Reentrenamiento RÁPIDO (5-10 min) — Recomendado para mantenimiento rutinario

Usa `best_params.joblib` existente del último tuning Optuna. Mismos hiperparámetros, datos frescos.

```bash
uv run python -m src.ai.trainer --symbol ALL --timeframe 5m
```

Busca estas líneas en el output:
```
🎯 Precisión CV: 97.XX% ± X.XX%
📈 Precisión final (15% hold-out): 99.XX%
✅ Modelo guardado: src/ai/models/xgboost_v1_1.joblib
```

---

## Paso 4b: Reentrenamiento COMPLETO con Tuning Bayesiano (30-60 min) — Usa cuando:
- Accuracy bajó significativamente
- Más de 2 meses desde el último run de Optuna
- Cambiaste `MODEL_FEATURES` o `LABEL_THRESHOLD`

```bash
uv run python -m src.ai.trainer --symbol ALL --timeframe 5m --tune --trials 50
```

Esto ejecuta búsqueda Bayesiana de Optuna sobre `n_estimators`, `learning_rate`, `max_depth`, `subsample`, `colsample_bytree`. Los nuevos mejores parámetros se guardan en `best_params.joblib`.

---

## Paso 5: Verificar que accuracy es aceptable

Del output del trainer, verifica:
- **Accuracy CV por símbolo:** Debe ser >90% para todos los símbolos
- **Accuracy hold-out:** Debe ser >85%
- DOT/USDT típicamente tiene el accuracy más bajo (~96%) — esto es esperado

Si algún símbolo es <85%, verifica la calidad de los datos (vacíos, outliers) y considera re-ejecutar con `--tune`.

---

## Paso 6: Ejecutar suite de tests

```bash
uv run test
```

Todos los 50+ tests deben pasar. Si fallan tests relacionados con el modelo, verifica que `xgboost_v1_1.joblib` fue creado correctamente.

---

## Paso 7: Reiniciar el engine

```bash
uv run engine
```

El engine carga el modelo al iniciar. Verifica en los logs:
```
🧠 SysMho: Sistema Neuronal Iniciado...
✅ Modelo XGBoost cargado
```

---

## Rollback (si algo sale mal)

```bash
# Restaura el backup
cp src/ai/models/xgboost_v1_1_backup_YYYYMMDD.joblib \
   src/ai/models/xgboost_v1_1.joblib

uv run engine  # Reinicia con modelo viejo
```

---

## Enlaces Relacionados
- `docs/adr/ADR-001-xgboost-architecture.md` — Por qué XGBoost
- `docs/adr/ADR-002-sliding-window-training.md` — Por qué ventana de 3 meses
- `.claude/rules/model-guard.md` — Regla model-guard
- `src/ai/trainer.py` — Implementación de reentrenamiento
