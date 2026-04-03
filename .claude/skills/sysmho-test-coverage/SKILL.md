---
name: sysmho-test-coverage
description: Maps which modules have tests and which critical functions are not covered. Use when deciding which tests to write next.
allowed-tools: Read Grep Glob
---

## Step 1 — Module inventory

List all source modules using Glob: `src/**/*.py` — exclude `__init__.py` and `__pycache__`. Sort the list.

## Step 2 — Test inventory

List all test files using Glob: `tests/**/*.py`. Read the beginning of each test file to understand what it covers.

## Step 3 — Run tests and see current state

```bash
uv run pytest tests/ -v --tb=no -q
```

## Step 4 — Cross-reference modules vs tests

For each critical module, search for its name in `tests/` to determine if it has test coverage:
- `circuit_breaker`, `meta_evaluator`, `predictor`, `risk`, `trader`, `monitor`, `repository`, `features`, `gap_filler`

Read the tests found to understand depth of coverage.

## Step 5 — Identify critical functions without tests

Functions are critical if they:
- Make Binance calls (real money)
- Write to the DB (trades, positions, portfolio)
- Make autonomous decisions (MetaEvaluator, CircuitBreaker)
- Calculate PnL or position sizing

## Step 6 — Coverage report

```
TEST COVERAGE — SYSMHO
─────────────────────────────────────────────────────
MODULES WITH COVERAGE:
  ✅ circuit_breaker.py  → test_phase5.py (basic)
  ✅ predictor.py        → test_phase3.py
  ✅ features.py         → test_phase2.py
  ...

MODULES WITHOUT COVERAGE:
  ❌ meta_evaluator.py   — CRITICAL: makes autonomous decisions
  ❌ self_learner.py     — IMPORTANT: writes meta_stats.json
  ❌ gap_filler.py       — MODERATE: gap detection logic
  ❌ runtime_config.py   — LOW: simple file functions

CRITICAL FUNCTIONS WITHOUT TESTS:
  ❌ MetaEvaluator.evaluate() — approves/rejects real trades
  ❌ RiskManager.evaluate_signal() — calculates position sizing
  ❌ PositionMonitor._close_position() — closes with real money
  ❌ TradeExecutor.execute_trade() — sends orders to Binance

TESTS TO WRITE (by priority):
  1. test_meta_evaluator.py — mock stats and verify score
  2. test_risk_manager.py — verify position sizing and limits
  3. test_self_learner.py — verify win_rate update
  4. test_gap_filler.py — verify gap detection

Would you like me to generate the missing tests?
```
