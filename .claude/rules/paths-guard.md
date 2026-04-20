---
name: paths-guard
description: Enforce src/paths.py as single source of truth for all file paths. No hardcoded paths.
type: validation
severity: critical
---

# Paths Guard Rule

**Purpose**: Prevent hardcoded file paths throughout the codebase. All paths MUST be resolved via `src/paths.py`, which ensures:
- Relative to workspace root (never absolute)
- Centralized changes (if path moves, update ONE place)
- Cross-platform compatibility

---

## What This Rule Checks

### 1. **Model Paths**

❌ **FORBIDDEN** — Hardcoded:
```python
model = load('src/ai/models/xgboost_v1_1.joblib')
backup = 'src/ai/models/backup.joblib'
```

✅ **CORRECT** — Via paths.py:
```python
from src.paths import MODEL_PATH, BACKUP_MODEL_DIR

model = load(MODEL_PATH)
backup = join(BACKUP_MODEL_DIR, 'backup.joblib')
```

### 2. **Log Paths**

❌ **FORBIDDEN**:
```python
log_file = 'src/sysmho_brain.log'
```

✅ **CORRECT**:
```python
from src.paths import BRAIN_LOG_PATH

log_file = BRAIN_LOG_PATH
```

### 3. **Data & IPC Paths**

❌ **FORBIDDEN**:
```python
runtime_state = 'src/runtime_state.json'
market_data_cache = '/tmp/market_data.parquet'
```

✅ **CORRECT**:
```python
from src.paths import RUNTIME_STATE_PATH, MARKET_DATA_CACHE

runtime_state = RUNTIME_STATE_PATH
market_data_cache = MARKET_DATA_CACHE
```

---

## Centralized Paths (src/paths.py)

All paths are defined **once** in `src/paths.py`:

```python
# Example structure (read actual file for current list)
MODEL_PATH = 'src/ai/models/xgboost_v1_1.joblib'
BRAIN_LOG_PATH = 'src/sysmho_brain.log'
RUNTIME_STATE_PATH = 'src/runtime_state.json'
BACKUP_MODEL_DIR = 'src/ai/models/backups'
```

---

## When This Rule Blocks

- **Pre-commit hook**: If you hardcode a path like `/home/...` or `src/data/...` directly
- **Code review**: If AI detects string literals that look like paths

---

## Enforcement

**If violated**: Blocks commit + shows correct path to use.

Example:
```
❌ BLOCKED — Hardcoded path detected:
  File: src/ai/predictor.py:10
  Found: model_file = 'src/ai/models/xgboost_v1_1.joblib'
  
  Fix:
    1. Import: from src.paths import MODEL_PATH
    2. Use: model_file = MODEL_PATH
    3. Retry commit
```

---

## When You Need a NEW Path

1. **Add to `src/paths.py`** with clear name:
   ```python
   NEW_DATA_PATH = 'src/data/new_dataset.csv'
   ```

2. **Use it everywhere**:
   ```python
   from src.paths import NEW_DATA_PATH
   data = read_csv(NEW_DATA_PATH)
   ```

3. **Document in `src/AGENTS.md`** under "Paths" section

---

## Related Files

- `src/paths.py` — Define paths here
- `CLAUDE.md` — States "Paths: Always relative, centralized"
- `src/AGENTS.md` — Lists all critical paths
