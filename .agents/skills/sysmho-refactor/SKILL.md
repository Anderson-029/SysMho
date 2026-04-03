---
name: sysmho-refactor
description: Analyzes a module and lists concrete cleanup opportunities with code evidence — no changes without approval. Use when looking for refactoring targets.
allowed-tools: Read Grep Glob
---

The user indicates a module or area to refactor.
If nothing is indicated, ask which one they want to improve.

## Step 1 — Read the full module

Read the indicated file or files.

## Step 2 — Detect improvement opportunities

Analyze looking for:

**Duplicated code**: search for repeated patterns in `src/` — if the same logic appears in multiple places, it's a candidate for extraction.

**Functions that are too long** (>50 lines): identify them and propose splitting them.

**Complex logic that can be simplified**: nested conditionals, flag variables, etc.

**Unused imports**: read the `^from` and `^import` lines at the top and verify each import is actually used in the file body.

**Hardcoded constants** inside the file that should be in `src/constants.py`.

**Outdated comments**: comments that describe behavior different from the current code.

**Missing type hints** in public functions.

## Step 3 — Verify changes won't break anything

For each proposed change, verify:
- Does it change the public interface? (function names, parameters)
- Which files depend on what is being changed?

Search for the function name to be changed in `src/` to find all callers.

## Step 4 — Opportunity report

Present BEFORE touching anything:

```
MODULE: src/executor/trader.py
REFACTOR OPPORTUNITIES
─────────────────────────────────────────────────────
1. [LOW RISK] Remove redundant db.connect() in _log_trade() (line 366)
   Reason: the pool already exists. Safe but adds noise.
   Impact: 0 external files affected.

2. [LOW RISK] Extract SL/TP logic to _place_sl_tp()
   Reason: 20 lines repeated if additional logic is added.
   Impact: internal to the file only.

3. [MEDIUM RISK] Rename parameter 'risk_approved_data' → 'signal'
   Reason: name is too long and verbose.
   Impact: main.py line 593 calls execute_trade(dictamen).

Apply the changes? I can do all of them, or indicate which ones.
```

Wait for approval before modifying.

## Step 5 — Apply approved changes

Apply one by one using the Edit tool, verifying the import after each change:

```bash
uv run python -c "from src.MODULE import CLASS; print('✅')"
```
