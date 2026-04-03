---
name: sysmho-retrain
description: Orchestrates safe XGBoost retraining — verifies data, backs up old model, retrains and validates metrics. Use when the model needs retraining.
allowed-tools: Read Shell
---

Execute the SysMho XGBoost model retraining safely and with verification.

## Step 1 — Verify available data volume

Query the database (connection: `config/settings.py` → `DATABASE_URL`):

```sql
SELECT symbol, timeframe, COUNT(*) AS candles,
       MIN(open_time) AS from_date, MAX(open_time) AS to_date
FROM market_data
GROUP BY symbol, timeframe
ORDER BY symbol, timeframe;
```

If any symbol has fewer than 10,000 candles in 5m, warn before continuing.

## Step 2 — Verify the current model

Read the directory `src/ai/models/` and list files with their modification dates.

Show the current model and its modification date. Ask the user to confirm they want to replace it.

## Step 3 — Back up the current model

Copy `src/ai/models/xgboost_v1.joblib` to `src/ai/models/xgboost_v1_backup_YYYYMMDD_HHMM.joblib` before proceeding. Confirm the backup was created.

## Step 4 — Delete the old model

Remove `src/ai/models/xgboost_v1.joblib` before retraining. This is required when `MODEL_FEATURES` has changed — the old model cannot be used with a different feature set.

## Step 5 — Retrain

Ask the user: retrain with existing parameters or with new Optuna tuning?

**Option A — Fast** (uses existing `best_params.joblib`, ~5-10 min):
```bash
uv run python -m src.ai.trainer --symbol ALL --timeframe 5m
```

**Option B — Full** (new Bayesian tuning with Optuna, 50 trials, ~30-60 min):
```bash
uv run python -m src.ai.trainer --symbol ALL --timeframe 5m --tune --trials 50
```

## Step 6 — Verify result

Check that `src/ai/models/xgboost_v1.joblib` exists and has size > 0.

Show the performance metrics of the new model compared to the previous ones (Win Rate CV and Hold-out per asset — these are printed by the trainer).

## Step 7 — Verify the system can load the new model

```bash
uv run python -c "from src.ai.predictor import ModelPredictor; p = ModelPredictor(); print('✅ Model loaded correctly')"
```

## Final report

```
RETRAINING COMPLETED
Model before: backup_DATE.joblib
New model: xgboost_v1.joblib (X MB)
Duration: ~X minutes
Average metrics: WR CV X% | Hold-out X%
Status: ✅ Ready for production
```
