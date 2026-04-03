---
name: sysmho-model-eval
description: Evaluates and compares current XGBoost model against previous backups — shows prediction metrics per class, confidence distribution, real win rate, and emits a MEJORANDO/EMPEORANDO/ESTABLE verdict with evidence.
allowed-tools: Read, Shell
---

# sysmho-model-eval — Evaluación y Comparación de Modelos

Evalúa el modelo XGBoost actual y lo compara contra versiones anteriores (backups). Muestra métricas de predicción, distribución de confianza, tasa de acierto real sobre trades cerrados, y emite un veredicto con evidencia: **MEJORANDO** / **EMPEORANDO** / **ESTABLE**.

---

## PASO 1 — Inventario de Modelos

Lista todos los archivos `.joblib` en `src/ai/models/` con su tamaño y fecha de modificación:

```bash
ls -lht src/ai/models/*.joblib 2>/dev/null | awk '{print $5, $6, $7, $8, $9}'
```

Mostrar:
```
INVENTARIO DE MODELOS
────────────────────────────────────────────────────
Actual:    xgboost_v1.joblib                  (Abr 3, 14:42)   8.8 MB
Backup 1:  xgboost_v1_backup_20260403_1442    (Abr 3, 14:42)   8.8 MB
Backup 2:  xgboost_v1_backup_20260327_1830    (Mar 27, 18:30)  26.1 MB
────────────────────────────────────────────────────
Total: N modelos disponibles
```

---

## PASO 2 — Dataset de Validación Común

Conectar a la BD (`config/settings.py` → `DATABASE_URL`) y obtener las últimas 2,000 velas por símbolo:

```sql
SELECT symbol, timeframe, open_time, open, high, low, close, volume, atr_14
FROM market_data
WHERE timeframe = '5m'
ORDER BY open_time DESC
LIMIT 2000;
```

Ejecutar como script Python:

```bash
uv run python - << 'EOF'
import asyncio, asyncpg, os, sys
sys.path.insert(0, '.')
from config.settings import DATABASE_URL

async def main():
    conn = await asyncpg.connect(DATABASE_URL)
    rows = await conn.fetch("""
        SELECT symbol, timeframe, open_time, open, high, low, close, volume, atr_14
        FROM market_data
        WHERE timeframe = '5m' AND atr_14 IS NOT NULL
        ORDER BY open_time DESC
        LIMIT 2000
    """)
    await conn.close()
    symbols = set(r['symbol'] for r in rows)
    none_atr = sum(1 for r in rows if r['atr_14'] is None)
    print(f"✅ Dataset cargado: {len(rows)} velas | {len(symbols)} símbolos | {none_atr} sin ATR")

asyncio.run(main())
EOF
```

Verificar que hay al menos 200 velas con ATR válido. Si no, advertir y continuar.

---

## PASO 3 — Ingeniería de Features

Para el dataset de validación, calcular las features que usa el modelo. Ejecutar con el módulo `src/ai/features.py`:

```bash
uv run python - << 'EOF'
import sys
sys.path.insert(0, '.')
from src.ai.features import FeatureEngineer
import asyncpg, asyncio
from config.settings import DATABASE_URL

async def main():
    conn = await asyncpg.connect(DATABASE_URL)
    rows = await conn.fetch("""
        SELECT symbol, timeframe, open_time, open, high, low, close, volume, atr_14
        FROM market_data
        WHERE timeframe = '5m' AND atr_14 IS NOT NULL
        ORDER BY symbol, open_time DESC
    """)
    await conn.close()

    fe = FeatureEngineer()
    data = [dict(r) for r in rows]
    X, symbols_used = fe.build_features(data)
    print(f"✅ Features calculadas: {X.shape[0]} muestras × {X.shape[1]} features")
    print(f"   Símbolos: {symbols_used}")
    print(f"   Columnas: {X.columns.tolist()}")

asyncio.run(main())
EOF
```

---

## PASO 4 — Predicciones por Versión de Modelo

Para **cada modelo** encontrado en el Paso 1, ejecutar:

```bash
uv run python - << 'EOF'
import sys, os, joblib, glob
sys.path.insert(0, '.')
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, confusion_matrix
from src.ai.features import FeatureEngineer
import asyncpg, asyncio
from config.settings import DATABASE_URL

MODEL_DIR = "src/ai/models"
CLASS_NAMES = {0: 'WAIT', 1: 'BUY', 2: 'SELL'}

async def get_validation_data():
    conn = await asyncpg.connect(DATABASE_URL)
    rows = await conn.fetch("""
        SELECT symbol, timeframe, open_time, open, high, low, close, volume, atr_14
        FROM market_data
        WHERE timeframe = '5m' AND atr_14 IS NOT NULL
        ORDER BY symbol, open_time DESC
    """)
    await conn.close()
    return [dict(r) for r in rows]

async def main():
    data = await get_validation_data()
    fe = FeatureEngineer()
    X, _ = fe.build_features(data)

    if X is None or len(X) == 0:
        print("❌ No hay features válidas para evaluar")
        return

    models = sorted(glob.glob(f"{MODEL_DIR}/*.joblib"))
    results = []

    for model_path in models:
        name = os.path.basename(model_path)
        size_mb = os.path.getsize(model_path) / 1024 / 1024
        mtime = os.path.getmtime(model_path)

        try:
            clf = joblib.load(model_path)
            y_pred = clf.predict(X)
            y_proba = clf.predict_proba(X)

            # Distribución de confianza
            max_proba = y_proba.max(axis=1)
            conf_80 = (max_proba >= 0.80).sum() / len(max_proba) * 100
            conf_90 = (max_proba >= 0.90).sum() / len(max_proba) * 100
            conf_95 = (max_proba >= 0.95).sum() / len(max_proba) * 100
            conf_mean = max_proba.mean() * 100

            # Distribución de clases predichas
            unique, counts = np.unique(y_pred, return_counts=True)
            class_dist = dict(zip(unique, counts))
            buy_pct  = class_dist.get(1, 0) / len(y_pred) * 100
            sell_pct = class_dist.get(2, 0) / len(y_pred) * 100
            wait_pct = class_dist.get(0, 0) / len(y_pred) * 100

            results.append({
                'name': name,
                'size_mb': size_mb,
                'conf_mean': conf_mean,
                'conf_80': conf_80,
                'conf_90': conf_90,
                'conf_95': conf_95,
                'buy_pct': buy_pct,
                'sell_pct': sell_pct,
                'wait_pct': wait_pct,
                'n_samples': len(y_pred),
            })

            print(f"\n📦 {name} ({size_mb:.1f} MB)")
            print(f"   Muestras evaluadas:  {len(y_pred)}")
            print(f"   Confianza media:     {conf_mean:.1f}%")
            print(f"   Alta confianza >80%: {conf_80:.1f}% de señales")
            print(f"   Alta confianza >90%: {conf_90:.1f}% de señales")
            print(f"   Alta confianza >95%: {conf_95:.1f}% de señales")
            print(f"   Distribución clases: BUY={buy_pct:.1f}% | SELL={sell_pct:.1f}% | WAIT={wait_pct:.1f}%")

        except Exception as e:
            print(f"⚠️ {name}: No se pudo cargar — {e}")

asyncio.run(main())
EOF
```

---

## PASO 5 — Tasa de Acierto Real por Época de Modelo

Determinar cuándo se desplegó cada versión y cuántos trades ganó/perdió durante ese período:

```bash
uv run python - << 'EOF'
import asyncio, asyncpg, os, glob
sys.path.insert(0, '.')
import sys
from datetime import datetime
from config.settings import DATABASE_URL

async def main():
    MODEL_DIR = "src/ai/models"
    backups = sorted(glob.glob(f"{MODEL_DIR}/xgboost_v1_backup_*.joblib"))

    # Reconstruir línea de tiempo de deployments desde fechas de backup
    epochs = []
    for b in backups:
        name = os.path.basename(b)
        # Extraer fecha: xgboost_v1_backup_YYYYMMDD_HHMM.joblib
        try:
            parts = name.replace("xgboost_v1_backup_", "").replace(".joblib", "").split("_")
            dt_str = f"{parts[0]}_{parts[1]}"
            dt = datetime.strptime(dt_str, "%Y%m%d_%H%M")
            epochs.append((dt, b))
        except:
            pass

    epochs.sort(key=lambda x: x[0])

    conn = await asyncpg.connect(DATABASE_URL)

    print(f"\n{'Período':<30} {'Trades':>7} {'Ganados':>8} {'Win Rate':>9} {'PnL Medio':>10}")
    print("─" * 70)

    for i, (start_dt, backup_name) in enumerate(epochs):
        if i + 1 < len(epochs):
            end_dt = epochs[i + 1][0]
            rows = await conn.fetch("""
                SELECT COUNT(*) AS total,
                       COUNT(*) FILTER (WHERE pnl > 0) AS winners,
                       AVG(pnl) AS avg_pnl
                FROM trades
                WHERE status = 'CLOSED'
                  AND executed_at >= $1 AND executed_at < $2
            """, start_dt, end_dt)
        else:
            rows = await conn.fetch("""
                SELECT COUNT(*) AS total,
                       COUNT(*) FILTER (WHERE pnl > 0) AS winners,
                       AVG(pnl) AS avg_pnl
                FROM trades
                WHERE status = 'CLOSED'
                  AND executed_at >= $1
            """, start_dt)

        r = rows[0]
        total = int(r['total'] or 0)
        winners = int(r['winners'] or 0)
        win_rate = (winners / total * 100) if total > 0 else 0
        avg_pnl = float(r['avg_pnl'] or 0)
        label = os.path.basename(backup_name)[:30]

        print(f"{label:<30} {total:>7} {winners:>8} {win_rate:>8.1f}%  ${avg_pnl:>8.2f}")

    await conn.close()

asyncio.run(main())
EOF
```

---

## PASO 6 — Tabla Comparativa y Veredicto

Con los datos de los Pasos 4 y 5, construir la tabla final:

```
COMPARACIÓN DE VERSIONES
══════════════════════════════════════════════════════════════════════

Modelo                        │ Tamaño │ Conf>90% │ WR Real │ Trades
──────────────────────────────┼────────┼──────────┼─────────┼───────
xgboost_v1.joblib (Abr 3)     │  8.8MB │  19.2%   │  68.3%  │  47
backup_20260403_1442 (Abr 3)  │  8.8MB │  22.1%   │  65.9%  │  51
backup_20260327_1830 (Mar 27) │ 26.1MB │  27.5%   │  59.4%  │  43
──────────────────────────────┴────────┴──────────┴─────────┴───────

Tendencias:
  Confianza >90%:  27.5% → 19.2%  ↘ (-8.3 pp)  [✅ SALUDABLE: menos sobreajuste]
  Win Rate real:   59.4% → 68.3%  ↗ (+8.9 pp)  [✅ MEJOR rendimiento en mercado]
  Tamaño modelo:   26.1MB → 8.8MB ↘ (-66%)     [✅ Modelo más compacto y generalista]
```

**Criterios de veredicto:**
- `MEJORANDO`: Win rate real ↑ **y** confianza excesiva ↓ (menos >90%)
- `EMPEORANDO`: Win rate real ↓ **o** confianza excesiva ↑ sin más trades
- `ESTABLE`: Cambios <3 pp en win rate y <5 pp en distribución de confianza

---

## PASO 7 — Reporte Final

```
╔═══════════════════════════════════════════════════════════════════╗
║         SYSMHO — EVALUACIÓN DE MODELOS                           ║
║               [FECHA Y HORA ACTUAL]                              ║
╠═══════════════════════════════════════════════════════════════════╣
║                                                                   ║
║  VEREDICTO: ✅ MEJORANDO                                          ║
║                                                                   ║
║  Modelo actual:    xgboost_v1.joblib (Abr 3, 14:42)             ║
║  Referencia:       backup_20260327 (Mar 27)                      ║
║                                                                   ║
║  MÉTRICAS CLAVE:                                                  ║
║    Win Rate real:     59.4% → 68.3%   (+8.9 pp)   ↗             ║
║    Sobreconfianza:    27.5% → 19.2%   (-8.3 pp)   ↘ [Bueno]    ║
║    Tamaño modelo:     26.1MB → 8.8MB  (-66%)      ↘ [Bueno]    ║
║    PnL medio/trade:   +$8.12 → +$12.44 (+53%)     ↗             ║
║                                                                   ║
║  EVIDENCIA:                                                       ║
║    • 47 trades con modelo actual: 32 ganados / 15 perdidos       ║
║    • Optuna redujo max_depth 10→5, añadió gamma=0.059            ║
║    • Distribución confianza normalizada (menos predicciones      ║
║      con win_probability >0.95)                                  ║
║                                                                   ║
║  RECOMENDACIÓN: Continuar con modelo actual.                     ║
║  Monitorear win rate en los próximos 50 trades.                  ║
║                                                                   ║
╚═══════════════════════════════════════════════════════════════════╝
```

---

## Notas de Implementación

- Si hay **menos de 10 trades** en alguna época, marcar con `⚠️ Muestra insuficiente (N trades)` y excluirla del veredicto.
- Si solo hay **1 modelo** disponible (sin backups), omitir comparación y mostrar solo métricas actuales con `ℹ️ Sin versiones anteriores para comparar`.
- Si el modelo actual **no puede cargarse**, abortar con `❌ Modelo actual corrupto — ejecutar sysmho-retrain`.
- La conexión a la BD usa `DATABASE_URL` de `config/settings.py`. Nunca hardcodear credenciales.
