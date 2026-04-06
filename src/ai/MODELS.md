# 🧠 Modelos XGBoost — SysMho v15.2.0

## Visión General

SysMho usa **modelos XGBoost entrenados** para predecir movimientos de precios en Binance Futures. Cada modelo es un "cerebro" especializado que evalúa 27 features técnicas y decide si comprar (BUY), vender (SELL), o esperar (WAIT) en cada vela de 5 minutos.

---

## 📂 Modelos Disponibles

### **1. `xgboost_v1_1.joblib` (ACTIVO — 8.8 MB)**

**Rol en SysMho:**
- Modelo de producción actual
- Entrenado: 2026-04-06 con 10 activos (BTC, ETH, BNB, SOL, XRP, ADA, AVAX, LINK, DOT, POL)
- Datos: 654k+ velas por activo (series históricas 2020-2026)
- Feature set: 27 variables (momentos 5m + contexto 1h/4h + swarm intelligence)

**Arquitectura:**
```
Input: 27 features (rsi_14, macd, adx, bb_pband, vwap_dist, funding_rate, etc)
├─ Momentum (5m): rsi_14, stoch_rsi_k, macd_diff_pct
├─ Trend (5m): adx, adx_pos, bb_pband
├─ Normalized price: atr_pct, ema_21_dist, ema_200_dist, vwap_dist
├─ Futures: funding_rate, obi_20
├─ Swarm intelligence: swarm_rsi_avg, swarm_macd_avg, swarm_bull_ratio
├─ Macro 1h: h1_rsi_14, h1_macd_diff_pct, h1_adx, h1_bb_pband, h1_atr_pct
└─ Macro 4h: h4_rsi_14, h4_macd_diff_pct, h4_adx, h4_bb_pband, h4_atr_pct

Output: 3 clases (0=SELL, 1=WAIT, 2=BUY)
└─ Probabilidades: [P(SELL), P(WAIT), P(BUY)]
```

**Precisión (Cross-Validation):**
```
BTC/USDT: 92.67% ± 3.67%  ⭐ mejor
ETH/USDT: 87.90% ± 6.02%
BNB/USDT: 90.23% ± 8.75%
SOL/USDT: 86.54% ± 5.07%
XRP/USDT: 85.68% ± 8.12%
ADA/USDT: 82.67% ± 7.56%
AVAX/USDT: 87.66% ± 5.29%
LINK/USDT: 82.64% ± 7.67%
DOT/USDT: 87.44% ± 4.97%
POL/USDT: 80.55% ± 17.00%  ⚠️ varianza alta
```

**Dónde se usa:**
- `src/ai/predictor.py → ModelPredictor.predict_signal()` — carga este modelo al iniciar
- `src/main.py → _5min_scanner()` — evalúa cada vela 5m
- `src/main.py → _bounty_watcher()` — filtra señales de ultra-convicción (55%+)
- Dashboard `/api/latest_signal` — proporciona predicción actual

**Flujo en SysMho:**
```
1. FeatureEngineer.get_master_dataframe()
   └─ Calcula 27 features para última vela
   
2. ModelPredictor.predict_signal(current_data)
   └─ XGBoost.predict_proba() → [P(SELL), P(WAIT), P(BUY)]
   └─ Aplica filtros (inertia, strength ratio, conviction)
   └─ Retorna signal_int (0=SELL, 1=WAIT, 2=BUY)
   
3. RiskManager.evaluate_signal()
   └─ Posición sizing, notional cap 12%, exposure limit 50%
   
4. [MANUAL] Dashboard: aprobación humana
   [AUTONOMY] MetaEvaluator: score >= 0.52
   └─ CircuitBreaker: verifica max positions, max trades/día, drawdown
   
5. TradeExecutor.execute_trade()
   └─ Envia orden a Binance testnet (o mainnet)
```

---

### **2. `xgboost_v1_1_backup_20260406_1227.joblib` (ANTERIOR — 26 MB)**

**Rol en SysMho:**
- Versión anterior (pre-reentrenamiento)
- Guardada en XGBoost 3.0.0 (incompatible con 3.2.0)
- Mantenida como referencia histórica / rollback de emergencia

**Por qué existe:**
- Reentrenamiento 2026-04-06 identificó incompatibilidad XGBoost 3.0 → 3.2
- Backup preserva versión anterior por si se necesita comparación
- NO se usa en producción

**Cuándo usarla:**
- Solo si v1_1 es corrupto
- Para análisis histórico: comparar performance v1 vs v1_1
- NO tocar sin coordinación de equipo

---

### **3. `best_params.joblib` (HIPERPARÁMETROS — 138 B)**

**Rol en SysMho:**
- Hiperparámetros óptimos encontrados por Optuna en entrenamiento anterior
- Se cargan **cada vez que se reentrana** para mantener configuración probada

**Contenido:**
```python
{
  'n_estimators': 116,
  'max_depth': 5,
  'learning_rate': 0.19654438916766945,
  'subsample': 0.9669663505857677,
  'colsample_bytree': 0.6588812435756853,
  'gamma': 0.05924799560654216
}
```

**Dónde se usa:**
- `src/ai/trainer.py → ModelTrainer.train_model()` — carga estos params
- `src/ai/trainers/sequential.py → SequentialTrainer.train_model()` — instancia XGBClassifier(**best_params)
- Permite reentrenamiento rápido sin Optuna (5-10 min vs 30-60 min)

---

## 🔄 Cómo Trabaja Juntos el Ecosistema

```
src/ai/models/
├── xgboost_v1_1.joblib                    ← El CEREBRO actual (en producción)
├── xgboost_v1_1_backup_20260406_1227.joblib  ← Backup anterior (seguridad)
├── best_params.joblib                     ← Hiperparámetros (reentrenamiento rápido)
└── meta_stats.json                        ← Estadísticas runtime (SelfLearner actualiza cada trade)
```

**Flujo de Entrenam iento:**
```
src/ai/trainer.py
  └─ carga best_params.joblib
  └─ llama SequentialTrainer
      └─ para cada asset (BTC, ETH, ...):
         ├─ Carga datos de BD (market_data)
         ├─ Calcula features (FeatureEngineer)
         ├─ Entrena XGBoost(best_params) con TimeSeriesSplit (5 folds)
         └─ Genera validación cruzada
      └─ Guarda modelo entrenado → xgboost_v1_1.joblib
```

**Flujo de Predicción (en vivo):**
```
src/main.py (_5min_scanner loop, cada 5 min)
  └─ FeatureEngineer.get_master_dataframe(symbol='BTC/USDT')
      └─ Descarga últimas velas de BD
      └─ Calcula 27 features
  └─ ModelPredictor.predict_signal(current_data)
      └─ Carga xgboost_v1_1.joblib (una sola vez en __init__)
      └─ XGBoost.predict_proba() → [P(SELL), P(WAIT), P(BUY)]
      └─ Aplica filtros (inertia > 72% veta, strength >= 2.0, etc)
      └─ Retorna {"signal_int": 2, "signal_str": "BUY", "confidence": 0.63}
  └─ RiskManager.evaluate_signal()
      └─ Verifica posición sizing (notional cap 12%)
  └─ [MANUAL] Dashboard aprueba / rechaza
      [AUTONOMY] MetaEvaluator aprueba si meta_score >= 0.52
  └─ CircuitBreaker verifica límites
  └─ TradeExecutor.execute_trade()
      └─ Envía orden a Binance testnet
      └─ Guarda en tabla trades
```

---

## 📊 Comparativa de Versiones

| Aspecto | xgboost_v1 (viejo) | xgboost_v1_1 (actual) |
|---------|---|---|
| Guardado en | XGBoost 3.0.0 | XGBoost 3.2.0 |
| Compatible con código | ❌ Incompatible | ✅ Compatible |
| Tamaño | 8.8 MB | 8.8 MB |
| Fecha entrenamiento | 2026-04-03 | 2026-04-06 |
| Datos | 10 activos | 10 activos (650k+ velas) |
| CV Accuracy (BTC) | ❌ No testeable | 92.67% |
| En producción | ❌ No | ✅ Sí |
| Backup existente | — | Sí (26 MB) |

---

## 🚀 Cómo Trabajar con los Modelos

### **Para compañero (desarrollo/testing)**
```bash
# Clonar repo e inmediatamente tiene los modelos
git clone https://github.com/.../SysMho.git
cd SysMho
uv sync  # instala dependencias
uv run engine  # usa xgboost_v1_1.joblib automáticamente
```

### **Para reentrenamiento (si cambias features o datos)**
```bash
uv run sysmho-retrain
# o manual:
uv run python -m src.ai.trainer --symbol ALL --timeframe 5m
```

### **Para Optuna tuning (optimizar hiperparámetros)**
```bash
uv run python -m src.ai.trainer --symbol ALL --timeframe 5m --tune --trials 50
# Genera nuevo best_params.joblib
```

### **Para análisis de performance**
```bash
# Comparar v1 vs v1_1 (si necesitas):
# Renombra temporalmente v1_1 → v1_1_prod.joblib
# Renombra v1 backup → xgboost_v1_1.joblib
# Corre comparación
# Revertir
```

---

## ⚠️ Notas Críticas

1. **NO elimines `xgboost_v1_1.joblib`** — engine no funciona sin él
2. **Si cambias `MODEL_FEATURES` en constants.py**, debes reentrenar (viejo incompatible)
3. **`best_params.joblib` se actualiza en cada Optuna tuning** — mantener sincronizado con código
4. **`meta_stats.json` es runtime** — NO commit después de entrenar (SelfLearner lo actualiza constantemente)
5. **Backups generados (20260406_*) se pueden limpiar** — ocupan espacio, son solo seguridad temporal

---

## 📈 Próximas Mejoras (Phase 2)

- **Meta-modelo**: cuando 200+ trades acumulados, entrenar segundo XGBoost que aprenda "BOUNTY > REGULAR"
- **Multiframe XGBoost**: modelos separados por timeframe (5m / 1h / 4h) en lugar de uno unificado
- **Ensemble**: combinar v1_1 (actual) + meta-modelo para decisiones de ultra-alta confianza
