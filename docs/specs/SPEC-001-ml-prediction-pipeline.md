# SPEC-001: Pipeline de Predicción ML

| Campo | Valor |
|-------|-------|
| **Status** | Active |
| **Version** | v3 (28 features) |
| **Last Updated** | 2026-04-20 |
| **Owner** | Anderson |
| **Implemented in** | `src/ai/predictor.py`, `src/analysis/features.py`, `src/ai/trainer.py` |

---

## 1. Motivation

SysMho necesita clasificar señales de trading en tiempo real: cada 5 minutos, para 10 activos simultáneamente. La decisión (BUY, SELL, WAIT) debe tomarse con:
- **Latencia <10ms** — no puede bloquear el event loop asyncio que maneja 30 WebSocket feeds
- **Accuracy >85%** — señales incorrectas consumen capital en fees y pérdidas
- **Probabilidades calibradas** — si el modelo dice 60%, debe ganar ~60% de las veces
- **Adaptabilidad** — el mercado cripto cambia de régimen cada 2-3 meses

---

## 2. Goals

- Clasificar dirección de vela 5m con accuracy >85% por símbolo (validated: 96.6-100%)
- Latencia de inferencia <10ms por predicción en CPU estándar
- Adaptarse a cambios de régimen mediante retraining periódico (sliding window)
- Probabilidades calibradas: `confidence` refleja win rate real (validado vía SelfLearner)
- Señales de alta convicción (PREMIUM/BOUNTY) con confidence ≥55% y 3 tendencias alineadas

---

## 3. Non-Goals

- Predicciones tick-level (menor que 5 minutos) — demasiado ruido
- Multi-exchange arbitrage — SysMho opera exclusivamente en Binance Futures
- Options o spot trading — solo perpetuos
- Portfolio optimization global — el risk manager maneja sizing, no el predictor

---

## 4. Feature Set (28 Features)

Definidas en `src/constants.py` → `MODEL_FEATURES`. Todas normalizadas/escaladas.

### Group 1: Momentum 5m (3 features)

| Feature | Description | Range |
|---------|-------------|-------|
| `rsi_14` | RSI(14) — mide sobrecompra/sobreventa | [0, 1] |
| `stoch_rsi_k` | Stochastic RSI %K — RSI dentro de su propio rango | [0, 1] |
| `macd_diff_pct` | MACD line - Signal line, como % del precio | ~[-0.05, 0.05] |

### Group 2: Trend Strength 5m (3 features)

| Feature | Description | Range |
|---------|-------------|-------|
| `adx` | ADX(14) — fuerza de tendencia (no dirección) | [0, 1] normalized |
| `adx_pos` | +DI — presión compradora | [0, 1] normalized |
| `bb_pband` | Posición dentro de Bollinger Bands (%B) | [0, 1] |

### Group 3: Price Dynamics 5m (6 features)

| Feature | Description | Range |
|---------|-------------|-------|
| `atr_pct` | ATR como % del precio actual | [0, ~0.05] |
| `ema_21_dist` | Distancia al EMA21 como % del precio | ~[-0.1, 0.1] |
| `ema_200_dist` | Distancia al EMA200 como % del precio | ~[-0.3, 0.3] |
| `vwap_dist` | Distancia al VWAP como % del precio | ~[-0.1, 0.1] |
| `pct_change` | Cambio % de precio en la vela actual | ~[-0.05, 0.05] |
| `vol_change` | Cambio % en volumen vs media móvil de volumen | ~[-1, 5] |

### Group 4: Futures Context (2 features)

| Feature | Description | Range |
|---------|-------------|-------|
| `funding_rate` | Tasa de financiación Binance Futures | ~[-0.001, 0.001] |
| `obi_20` | Order Book Imbalance (20 niveles bid/ask) | [-1, 1] |

### Group 5: Swarm Intelligence (3 features)

Cross-symbol aggregates — contexto del portfolio completo (los otros 9 activos).

| Feature | Description |
|---------|-------------|
| `swarm_rsi_avg` | RSI promedio de los 10 activos del portfolio |
| `swarm_macd_avg` | MACD diff promedio del portfolio |
| `swarm_bull_ratio` | % de activos con RSI > 50 (0.0 = todos bajistas, 1.0 = todos alcistas) |

### Group 6: Macro Context 1h (5 features)

Same indicators as Group 1-2 but from the 1-hour timeframe, merged via `merge_asof()`:

`h1_rsi_14`, `h1_macd_diff_pct`, `h1_adx`, `h1_bb_pband`, `h1_atr_pct`

### Group 7: Macro Context 4h (5 features)

`h4_rsi_14`, `h4_macd_diff_pct`, `h4_adx`, `h4_bb_pband`, `h4_atr_pct`

### Group 8: Identity (1 feature)

| Feature | Description | Encoding |
|---------|-------------|----------|
| `symbol_encoded` | Stable integer ID for each asset | BTC=0, ETH=1, BNB=2, SOL=3, XRP=4, ADA=5, AVAX=6, LINK=7, DOT=8, POL=9 |

> Encoding is stable: adding a new symbol gets the next integer (10, 11...) without changing existing ones.

---

## 5. Model Architecture

```
Algorithm:     XGBoost (gradient boosted trees)
Task:          Multiclass classification (3 classes)
Classes:       SELL=0, WAIT=1, BUY=2
Objective:     softmax (outputs probabilities per class)

Hyperparameters (Optuna-tuned, saved in best_params.joblib):
  n_estimators:      235
  learning_rate:     0.1259
  max_depth:         5
  subsample:         0.8
  colsample_bytree:  0.9
  eval_metric:       mlogloss
  n_jobs:            -1 (all CPU cores)
  random_state:      42

Training strategy:
  Data:         Sliding window 3 months = 25,920 candles 5m per symbol
  Validation:   TimeSeriesSplit (5 folds, NO shuffle — preserves temporal order)
  Hold-out:     Last 15% of data (TRAIN_TEST_SPLIT=0.15)
  Class weight: Balanced via sample_weight (WAIT ~97%, BUY/SELL ~1.5% each)
  Label:        0.7% price movement in next candle (LABEL_THRESHOLD)
```

**Accuracy results (2026-04-20 retraining):**

| Symbol | CV Accuracy | Hold-out |
|--------|-------------|---------|
| BTC/USDT | 99.10% | 100.00% |
| ETH/USDT | 97.59% | 99.46% |
| BNB/USDT | 99.19% | 99.95% |
| SOL/USDT | 97.58% | 99.46% |
| XRP/USDT | 97.96% | 99.82% |
| ADA/USDT | 97.62% | 99.27% |
| AVAX/USDT | 97.75% | 98.96% |
| LINK/USDT | 97.53% | 99.46% |
| DOT/USDT | 95.99% | 96.60% |
| POL/USDT | 97.66% | 99.25% |

---

## 6. Signal Filters (post-prediction, in order)

Applied in `ModelPredictor.predict_signal()` (`src/ai/predictor.py`):

### Filter 1: Inertia Filter
```
if p(WAIT) > NORMAL_INERTIA_THRESHOLD (0.72):
    return WAIT  # Prevents overtrading in uncertain conditions
```

### Filter 2: Dominant Class Selection
```
dominant = argmax(p_BUY, p_SELL)
opposite = min(p_BUY, p_SELL)
```

### Filter 3: Strength Ratio
```
if dominant / opposite < NORMAL_STRENGTH_RATIO (2.0):
    return WAIT  # Signal not strong enough relative to opposite direction
```

### Filter 4: Minimum Confidence
```
if dominant_prob < NORMAL_MIN_CONFIDENCE (0.38):
    return WAIT
```

### Signal Type Classification
```
if dominant_prob >= HIGH_CONVICTION_THRESHOLD (0.55):
    signal_type = "PREMIUM"  # Eligible for BOUNTY watcher
else:
    signal_type = "STANDARD"
```

---

## 7. Alternatives Considered

| Alternative | Why Rejected |
|-------------|--------------|
| LSTM (seq2seq) | Latency 100-500ms; overfitting on <100k samples per symbol; requires GPU |
| Transformer (Temporal Fusion) | Same as LSTM; overkill for tabular financial data |
| Random Forest | No calibrated probabilities; slightly lower accuracy |
| Rule-based (RSI thresholds) | No adaptation to market regime changes; high noise in ranging markets |
| Logistic Regression | Too simple; can't capture non-linear feature interactions |
| Online learning (SGD) | No reliable `predict_proba` calibration; unstable during regime shifts |

---

## 8. Known Limitations

1. **Class imbalance:** WAIT accounts for ~97% of all candles. Mitigated by `sample_weight`, but BUY/SELL precision is lower than WAIT precision.

2. **Market regime sensitivity:** Model trained on last 3 months may fail after major structural changes (regulatory shocks, exchange failures, macroeconomic events outside the training window).

3. **Funding rate gaps:** `obi_20` and `funding_rate` data may have gaps during Binance maintenance windows. These are filled with the previous value (forward-fill).

4. **Cold start for MetaEvaluator:** First 10 trades per symbol go without the MetaEvaluator filter (insufficient statistical data). Quality may be lower during this period.

5. **DOT/USDT lower accuracy:** DOT has higher inherent volatility and less predictable patterns. CV accuracy ~96% vs ~98% for other symbols.

---

## 9. Operational Notes

### Routine retraining (every 1-2 weeks)
```bash
# See full guide: docs/how-to/HOW-TO-retrain-model.md
uv run python -m src.ai.trainer --symbol ALL --timeframe 5m
```

### Retraining with Bayesian hyperparameter tuning (every 2-3 months)
```bash
uv run python -m src.ai.trainer --symbol ALL --timeframe 5m --tune --trials 50
```

### Check current model metrics
```bash
/sysmho-metrics
```

### Monitor prediction quality
```bash
/sysmho-performance  # Win rate, PnL, calibration
/sysmho-logs         # Real-time brain decisions
```

### Model files location
```
src/ai/models/
├── xgboost_v1_1.joblib          # Active production model
├── best_params.joblib           # Latest Optuna hyperparameters
├── meta_stats.json              # SelfLearner statistics (win rates by context)
└── xgboost_v1_1_backup_*.joblib # Previous model backups
```

---

## 10. Future Work

- **Phase 2 meta-model:** After 200+ autonomous trades, train a second-level model on `meta_stats` data to replace the hand-crafted MetaEvaluator heuristics
- **Feature importance tracking:** Monitor which features degrade over time (`/sysmho-feature-importance`, currently planned)
- **Regime detection:** Auto-detect market regime changes and trigger retraining proactively
- **Online learning layer:** Small SGD model on top of XGBoost for real-time adaptation without full retraining
