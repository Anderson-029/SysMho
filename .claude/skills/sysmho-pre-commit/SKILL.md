---
name: sysmho-pre-commit
description: Pre-save consistency checklist — versions, SQL injection risks, stale constants, dead imports. Use before committing changes.
allowed-tools: Read Grep Glob
---

Run this complete checklist before considering a change ready to commit.

## CHECK 1 — Consistent version

Search for `SYSMHO_VERSION` and version strings like `v15` in `src/` Python files.

Verify all version references are identical.

## CHECK 2 — SQL without bound parameters (injection risk)

Search for f-strings containing SQL keywords (SELECT, INSERT, UPDATE, DELETE) in `src/` Python files:

Pattern to look for: `f".*SELECT`, `f".*INSERT`, `f".*{` in SQL context.

Any SQL query built with f-strings or string concatenation is an alert.

## CHECK 3 — Hardcoded constants outside constants.py

Search for numeric values that appear in `src/` Python files that are NOT in `constants.py` and are NOT in test files, comments, logs, or sleep calls.

Flag numbers that look like thresholds or business rules (percentages, limits, ratios).

## CHECK 4 — Comments that don't match the code

Read the recently modified files and verify:
- Percentages in comments that no longer match the code
- Variable/function names mentioned in comments that no longer exist
- References to old versions or deprecated fields

Search for potentially stale references: `25%`, `MATIC`, `trade_history`, `pnl_usdt`, `confidence.*direction`.

## CHECK 5 — Unused imports

For each modified file, read the import lines at the top and verify each import appears at least once in the file body.

## CHECK 6 — Orphan files (not imported by anyone)

For each Python file in `src/` (excluding `__init__.py`), verify that its module name is referenced by at least one other file in `src/`. Files with zero references are orphan candidates.

## CHECK 7 — Interface coherence

If a public function was changed, verify all callers use the new signature — search for the function name in `src/`.

## Final report

```
PRE-COMMIT CHECKLIST — [DATE]
─────────────────────────────────────────────────────
✅ Version consistent: 15.2.0
❌ Potential SQL injection: repository.py:330 (time_filter)
✅ No new hardcoded constants
⚠️ Outdated comment: risk/manager.py:177 ("Max 25%")
✅ No dead imports detected
✅ No new orphan files

VERDICT: 2 ITEMS TO RESOLVE BEFORE COMMIT
```
