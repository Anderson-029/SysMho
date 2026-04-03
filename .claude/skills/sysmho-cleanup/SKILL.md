---
name: sysmho-cleanup
description: Cleans the codebase by removing dead code, unused imports, unconsumed indicators, orphan files — always with evidence and confirmation. Use when reducing technical debt.
allowed-tools: Read Grep Glob
---

Audit and clean the SysMho codebase. Work in successive passes: first detect everything, then apply by category with confirmation.

## PASS 1 — Detect orphan files

Using Glob, list all Python files in `src/` (excluding `__init__.py` and `__pycache__`).

For each file, search in `src/` for any `from ... import` or `import ...` reference to that file's module name. Files with zero references from other files are orphan candidates — list them.

## PASS 2 — Detect technical indicators not used by the model

Read `src/constants.py` to get `MODEL_FEATURES`.
Read `src/analysis/indicators.py` to see all indicators calculated by `add_all_indicators()`.

Compare: which columns does `add_all_indicators()` produce but are NOT in `MODEL_FEATURES` and NOT in the `h1_`, `h4_` prefixes used by `features.py`?

Indicators with no consumer are candidates for removal.

## PASS 3 — Detect dead imports in each file

For each Python file in `src/`, read the import lines at the top and check whether each imported name appears in the file body. If an import appears only once (in the import statement itself), flag it as a potential dead import.

Limit output to the 40 most suspicious cases.

## PASS 4 — Detect obsolete API fields

Search in `src/` for lines containing comments like: `compatibilidad`, `deprecated`, `obsoleto`, `ya no se usa`, `dead`, `unused`.

## PASS 5 — Detect constants defined but not used

Read `src/constants.py` and get all constant names (UPPER_CASE = ...).

For each constant, search in `src/` (excluding `constants.py` itself) to see if it is referenced anywhere. Constants with zero references are candidates for removal.

## PASS 6 — Detect functions possibly never called

Read function definitions (`def function_name(`) across `src/` files. For each function, count references in `src/`. Functions appearing only once (in their definition) are candidates — but verify they are not public API called from tests or external tools.

## PRESENT FULL REPORT

Before deleting ANYTHING, present everything found:

```
CODEBASE CLEANUP — SYSMHO [DATE]
─────────────────────────────────────────────────────
ORPHAN FILES (not imported by the system):
  src/collector/market_data.py — 0 imports found

INDICATORS WITHOUT MODEL CONSUMER:
  indicators.py calculates but MODEL_FEATURES does not use:
  - williams_r
  - stoch_rsi_d
  - ema_9, ema_50
  - adx_neg

OBSOLETE API FIELDS:
  portfolio.py:138 — "pnl_global" marked "for compatibility"

UNUSED CONSTANTS:
  [list if found]

POSSIBLY DEAD FUNCTIONS:
  [list if found]

─────────────────────────────────────────────────────
CLEANUP PLAN (low to high risk):

  SAFE (zero impact):
  □ Remove "for compatibility" fields from API responses
  □ Remove dead imports in individual files
  □ Update incorrect comments

  MODERATE (verify first):
  □ Remove unused indicators from indicators.py
    → Confirm no test checks them directly
  □ Remove orphan files
    → Confirm no external script calls them

  REQUIRES ANALYSIS:
  □ Remove functions with no callers
    → May be public APIs used from tests or outside src/

─────────────────────────────────────────────────────
Which categories do you want to clean?
Options: "all", "safe only", or specific items.
```

## EXECUTE CLEANUP

Only when the user approves:

1. For each approved item, read the affected file completely first
2. Apply the change with the Edit tool
3. Verify the module imports correctly:

```bash
uv run python -c "
from src.analysis.indicators import TechnicalIndicators
from src.ai.predictor import ModelPredictor
print('✅ Imports OK')
"
```

4. If there are related tests, run only those tests:

```bash
uv run pytest tests/ -v --tb=short -q
```

5. Record what was removed and why in a summary at the end.

## POST-CLEANUP SUMMARY

```
CLEANUP COMPLETED
─────────────────────────────────────────────────────
Removed:
  ✅ indicators.py — N unused indicators (-X lines)
  ✅ portfolio.py — obsolete pnl_global field (-2 lines)
  ✅ market_data.py — orphan file (-X lines)

Total reduction: ~X lines of dead code
Tests: all pass ✅
Imports: all OK ✅
```
