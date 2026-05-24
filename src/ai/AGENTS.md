# AGENTS.md — src/ai/

> **Navigation:** `CLAUDE.md` (manifest) → `AGENTS.md` (skills index) → `src/AGENTS.md` (module architecture) → This file (ML pipeline)
>
> **When to read:** Working with XGBoost model, training pipeline, MetaEvaluator logic, or SelfLearner statistics. Also see `src/ai/MODELS.md` for brain architecture.
> **Loading strategy:** On-demand — loaded only when you need ML context (not preloaded).

---

## Pipeline

```
PostgreSQL (market_data, sentiment_data, gemini_market_context)
  │
  ├─ FeatureEngineer.get_master_dataframe()  [analysis/features.py]
  │   └── TechnicalIndicators.add_all_indicators()
  │   └── macro context injection (1h / 4h merge_asof)
  │   └── institutional features (funding_rate, obi_20)
  │   └── swarm intelligence (cross-symbol RSI/MACD averages)
  │   └── 28 feature vector (MODEL_FEATURES from constants.py)
  │
  ├─ ModelPredictor.predict_signal()  [ai/predictor.py]
  │   └── XGBoost predict_proba → [P(SELL), P(WAIT), P(BUY)]
  │   └── Inertia filter (WAIT > 72% → veto)
  │   └── Strength ratio (dominant/opposite ≥ 2.0)
  │   └── High conviction flag (≥ 55% → BOUNTY)
  │
  ├─ RiskManager.evaluate_signal()  [risk/manager.py]
  │   └── Position sizing, Notional Cap 12%, Exposure Limit 50%
  │
  ├─ GeminiIntelligenceAgent.get_context_report()  [intelligence/gemini_agent.py]
  │   └── Investigates web sources at 3:45 of cycle
  │   └── Returns: sentiment_score, whale_pressure, macro_bias, news_risk_level, optimal_hour, llm_veto
  │
  └─ [MANUAL] Dashboard approval  |  [AUTONOMOUS] MetaEvaluator (6 components) + CircuitBreaker
        └── MetaEvaluator combines:
        │    1. Global win rate
        │    2. Hourly win rate
        │    3. Confidence calibration
        │    4. Loss streak penalty
        │    5. Base confidence
        │    6. Gemini context score  ← NEW
        └── If Gemini llm_veto=True → blocks regardless of XGBoost
        └── TradeExecutor.execute_trade()  [executor/trader.py]
```

---

## Model

| Property | Value |
|----------|-------|
| Algorithm | XGBoost (multi-class) |
| Version | v3 (retrained with Gemini features) |
| Classes | 0=SELL, 1=WAIT, 2=BUY |
| Features | 28 (27 technical/macro + 1 Gemini context—see `MODEL_FEATURES` in `src/constants.py`) |
| Assets | 10 (BTC, ETH, BNB, SOL, XRP, ADA, AVAX, LINK, DOT, POL — all /USDT) |
| CV strategy | TimeSeriesSplit 5-fold |

**Feature groups**:
- Momentum 5m: `rsi_14`, `stoch_rsi_k`, `macd_diff_pct`
- Trend 5m: `adx`, `adx_pos`, `bb_pband`
- Normalized price: `atr_pct`, `ema_21_dist`, `ema_200_dist`, `vwap_dist`, `pct_change`, `vol_change`
- Futures: `funding_rate`, `obi_20`
- Swarm intelligence: `swarm_rsi_avg`, `swarm_macd_avg`, `swarm_bull_ratio`
- Macro 1h: `h1_rsi_14`, `h1_macd_diff_pct`, `h1_adx`, `h1_bb_pband`, `h1_atr_pct`
- Macro 4h: `h4_rsi_14`, `h4_macd_diff_pct`, `h4_adx`, `h4_bb_pband`, `h4_atr_pct`

---

## Model Files

| File | Contents | Status |
|------|----------|--------|
| `src/ai/models/xgboost_v1_1.joblib` | **ACTIVE** — Serialized model (tuple: xgb_model, feature_names) | ✅ Current (26M) |
| `src/ai/models/xgboost_v1.joblib` | Previous version — kept for reference/comparison only | 📦 Archived (8.8M) |
| `src/ai/models/best_params.joblib` | Optimal hyperparameters from Optuna (n_estimators=235, max_depth=5, lr=0.1259, subsample=0.667, colsample=0.788, gamma=1.53e-05) | ✅ Used by trainer |
| `src/ai/models/meta_stats.json` | SelfLearner statistics cache — written by `self_learner.py`, read by `meta_evaluator.py` | ✅ Live |

**Model switching**: `src/paths.py` → `MODEL_PATH = ...xgboost_v1_1.joblib`. To compare against v1: temporarily change `MODEL_PATH` and restart.

**If you change `MODEL_FEATURES`**: delete all `.joblib` before retraining — old models are incompatible with different feature sets.

---

## Training

```bash
# Fast retraining (uses existing best_params.joblib, ~5-10 min)
uv run python -m src.ai.trainer --symbol ALL --timeframe 5m

# Full retraining with new Bayesian tuning (50 Optuna trials, ~30-60 min)
uv run python -m src.ai.trainer --symbol ALL --timeframe 5m --tune --trials 50
```

Training is incremental per asset (sequential multi-asset XGBoost with a single shared model). Uses `TimeSeriesSplit` — never shuffles time-series data.

For orchestrated retraining with safety checks, use the `sysmho-retrain` skill.

---

## MetaEvaluator

**File**: `src/ai/meta_evaluator.py`

The second-layer statistical filter that decides autonomous approval. Evaluates 6 components:

| Component | What it measures | Source |
|-----------|-----------------|--------|
| Global win rate | Historical win rate of closed trades | meta_stats.json |
| Hourly win rate | Win rate by UTC hour and direction for this symbol | meta_stats.json |
| Confidence calibration | Predicted confidence vs actual outcome alignment | meta_stats.json |
| Loss streak | Recent consecutive losses (penalizes after bad streaks) | recent trades |
| Base confidence | Raw XGBoost confidence of the signal | XGBoost output |
| **Gemini context** | **Market sentiment, whale pressure, macro bias, news risk** | **gemini_market_context table** |

**Gemini component** (NEW in v15.3.0):
- Calculates weighted score from: `sentiment_norm * 0.30 + whale_norm * 0.25 + macro_norm * 0.25 + news_norm * 0.10 + hour_score * 0.10`
- **Immediate veto**: If `llm_veto=True` and `GEMINI_VETO_BLOCKS_TRADE=True` → returns `(0.0, False)` (trade blocked regardless of XGBoost confidence)
- **Fallback**: If Gemini unavailable/timeout → falls back to 5-component scoring (zero regression)

**Threshold**: `meta_score >= META_SCORE_THRESHOLD` (default `0.52` in `constants.py`) → APPROVED. Below → REJECTED.

Reads from:
- `src/ai/models/meta_stats.json` (stats reloaded after each closed trade)
- `src/database/gemini_market_context` (latest Gemini report fetched before evaluation)

---

## SelfLearner

**File**: `src/ai/self_learner.py`

Updates `meta_stats.json` after each trade closure. Records:
- Global win rate per symbol
- Win rate by hour (UTC) and direction
- Confidence calibration buckets (predicted vs actual)

**Phase 2 (pending)**: When 200+ trades are available with Gemini context, train a second-level XGBoost meta-model on these 6 components — replacing the heuristic scoring with a learned decision boundary.
