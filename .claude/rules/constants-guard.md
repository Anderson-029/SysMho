---
name: constants-guard
description: Enforce constants.py as single source of truth for all thresholds, features, timeframes, symbols
type: validation
severity: critical
---

# Constants Guard Rule

**Purpose**: Prevent hardcoded numeric parameters throughout the codebase. All thresholds, symbols, feature lists, and timeframes MUST be referenced from `src/constants.py`.

---

## What This Rule Checks

### 1. **Thresholds & Magic Numbers**

❌ **FORBIDDEN** — Hardcoded in source code:
```python
if rsi > 70:  # ← Magic number
    signal = 'SELL'

if invested > 500:  # ← Magic number
    position_too_large = True
```

✅ **CORRECT** — Referenced from constants:
```python
from src.constants import RSI_OVERBOUGHT, MAX_POSITION_SIZE

if rsi > RSI_OVERBOUGHT:
    signal = 'SELL'

if invested > MAX_POSITION_SIZE:
    position_too_large = True
```

### 2. **Symbols & Timeframes**

❌ **FORBIDDEN**:
```python
symbols = ['BTC/USDT', 'ETH/USDT', ...]  # Duplicated
default_timeframe = '5m'  # Duplicated
```

✅ **CORRECT**:
```python
from src.constants import SYMBOLS, DEFAULT_TIMEFRAME

for symbol in SYMBOLS:
    ...
```

### 3. **Model Features**

❌ **FORBIDDEN**:
```python
features = ['rsi_14', 'macd_diff', ...]  # Hardcoded list
```

✅ **CORRECT**:
```python
from src.constants import MODEL_FEATURES

features = MODEL_FEATURES  # Or iterate through it
```

---

## Where Constants Live

Reference: `src/constants.py` — Single source of truth for:
- `SYMBOLS` (portfolio of 10 assets)
- `DEFAULT_TIMEFRAME` / `MACRO_TIMEFRAMES`
- `MODEL_FEATURES` (27 features)
- All numeric thresholds (RSI, Circuit Breaker, etc.)

---

## When This Rule Blocks

- **Pre-commit hook**: If you commit code with hardcoded thresholds/symbols
- **Code review**: If AI detects magic numbers in imports/functions
- **Feature engineering**: If you try to hardcode feature names

---

## Enforcement

**If violated**: Blocks commit + provides suggestion to move value to `constants.py`.

Example:
```
❌ BLOCKED — Hardcoded threshold detected:
  File: src/ai/predictor.py:45
  Found: if confidence > 0.55:  # Magic number
  
  Fix: 
    1. Add to constants.py: MIN_CONFIDENCE = 0.55
    2. Import in predictor.py
    3. Use: if confidence > MIN_CONFIDENCE:
    4. Retry commit
```

---

## Related Files

- `src/constants.py` — Define here
- Any file that uses the constant — Import from constants
- `CLAUDE.md` — States "Constants: Single source of truth"
