---
name: model-guard
description: Prevent model incompatibility when MODEL_FEATURES changes. Delete old .joblib before retraining.
type: validation
severity: critical
---

# Model Guard Rule

**Purpose**: Prevent model poisoning when `MODEL_FEATURES` in `src/constants.py` changes. XGBoost models are incompatible with different feature sets — this rule ensures you CANNOT accidentally use an old model with new features.

---

## The Problem

### Scenario: Incompatible Model State

```
Step 1 — Train model with 27 features:
  MODEL_FEATURES = [rsi_14, macd_diff, adx, ..., h4_atr_pct]  # 27
  xgboost_v1_1.joblib created with 27 features

Step 2 — Someone changes MODEL_FEATURES:
  MODEL_FEATURES = [rsi_14, macd_diff, adx, ..., h4_atr_pct, h1_rsi_21]  # 28
  But xgboost_v1_1.joblib STILL expects 27

Step 3 — Prediction runs:
  Input: 28 features
  Model: "I expect 27!"
  Output: ❌ CRASH — Feature mismatch error
  
  Impact: 
    - Trading engine stops
    - Silent failure (crash not obvious)
    - Potential losses if positions are open
```

---

## What This Rule Prevents

### ❌ Blocked Actions:

**Commit with MODEL_FEATURES changed + old .joblib present:**
```python
# src/constants.py (CHANGED)
MODEL_FEATURES = [  # ← Now 28 features instead of 27
    'rsi_14',
    'stoch_rsi_k',
    ...
    'h4_atr_pct',
    'h1_rsi_21'  # ← NEW
]
```

If `.joblib` files still exist (trained with 27 features), rule **BLOCKS** and says:

```
❌ BLOCKED — MODEL_FEATURES changed but old model exists:
  
  Changes detected:
    - Old: 27 features
    - New: 28 features
    - Incompatible!

  Action required BEFORE retraining:
    1. rm src/ai/models/xgboost_v1_1.joblib
    2. rm src/ai/models/xgboost_v1_1_backup_*.joblib
    3. uv run sysmho-retrain
    4. Retry commit
```

---

## How to Use This Rule

### **Scenario 1: Add a Feature**

```bash
# 1. Edit constants.py and add h1_rsi_21
vi src/constants.py

# 2. Try to commit
git commit -m "feat: add h1_rsi_21 feature"

# 3. model-guard.md DETECTS change and BLOCKS:
# ❌ MODEL_FEATURES changed from 27 to 28
#    Delete old models and retrain

# 4. Clean old models
rm src/ai/models/xgboost_v1_1.joblib
rm src/ai/models/xgboost_v1_1_backup_*.joblib

# 5. Retrain with NEW features
uv run sysmho-retrain

# 6. NOW commit succeeds ✅
git commit -m "feat: add h1_rsi_21 feature"
```

### **Scenario 2: Remove a Feature**

Same process — delete old models, retrain, then commit.

### **Scenario 3: Change Feature Name**

Same process — XGBoost is strict about feature order and names.

---

## Feature Compatibility Table

| ACTION | OLD .joblib | NEW .joblib | RULE STATUS |
|--------|------------|-----------|------------|
| No change to MODEL_FEATURES | 27 features | (none) | ✅ OK, old model works |
| Add 1 feature (27→28) | 27 features | (need new) | ❌ BLOCKS until old deleted |
| Remove 1 feature (27→26) | 27 features | (need new) | ❌ BLOCKS until old deleted |
| Reorder features | 27 features (old order) | (need new) | ❌ BLOCKS until old deleted |
| Change feature calc | 27 features | 27 features | ⚠️ WARNS (same shape, different values) |

---

## When This Rule Triggers

- **Pre-commit hook**: If you edited `src/constants.py` AND MODEL_FEATURES size changed
- **CI/CD**: If retraining starts with incompatible feature set
- **Manual check**: Via `/sysmho-pre-commit` skill

---

## Bypassing This Rule (NOT RECOMMENDED)

If you absolutely must force train with old models (testing only):

```bash
# This forces retraining WITHOUT deleting old model
# ⚠️ Only for local testing, NEVER in production
uv run python -m src.ai.trainer --symbol ALL --timeframe 5m --force
```

**Consequences of forcing**:
- New model trained on new features
- Old backup might be loaded by mistake
- Silent failures possible

---

## Best Practice

1. **Never change MODEL_FEATURES lightly**
   - Changes should be data-driven (feature importance analysis)
   - Each change should be tested on local backtest first

2. **Always follow the flow**:
   - Decide to add/remove feature
   - Edit `src/constants.py`
   - Delete old models
   - Retrain
   - Test locally
   - Commit

3. **Document the change**:
   ```
   git commit -m "feat: add h1_rsi_21 to improve macro context
   
   MODEL_FEATURES: 27 → 28 features
   Old models deleted and retrained.
   New accuracy: 87.2% (vs 86.47% before)
   "
   ```

---

## Related Files

- `src/constants.py` — Define MODEL_FEATURES here
- `src/ai/trainer.py` — Retraining logic
- `src/ai/predictor.py` — Uses MODEL_FEATURES for predictions
- `src/ai/AGENTS.md` — ML pipeline details
