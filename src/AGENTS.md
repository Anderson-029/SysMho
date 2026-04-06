# AGENTS.md — src/ Module Architecture

> Parent context: `AGENTS.md` (workspace root)

---

## Module Map

| Directory | Responsibility | Main Files |
|-----------|---------------|------------|
| `ai/` | ML pipeline: predict, train, evaluate, self-learn | `predictor.py`, `trainer.py`, `meta_evaluator.py`, `self_learner.py`, `backtest.py` |
| `analysis/` | Technical indicators and feature engineering (27 features) | `indicators.py`, `features.py` |
| `collector/` | Real-time data collection from Binance (always mainnet) | `websocket.py`, `market_data.py`, `backfill.py`, `gap_filler.py` |
| `dashboard/` | FastAPI REST API + Vanilla JS frontend on port 8000 | `api.py`, `deps.py`, `routes/`, `static/` |
| `database/` | asyncpg repository, DDL schema, SQL migrations | `repository.py`, `schema.sql`, `migration_v*.sql` |
| `executor/` | Trade execution, position monitoring, circuit breaker | `trader.py`, `monitor.py`, `circuit_breaker.py` |
| `risk/` | Signal auditing: position sizing, notional cap, exposure | `manager.py` |

---

## Entry Points

| Process | File | Command | Env file loaded |
|---------|------|---------|-----------------|
| AI Engine | `src/main.py` | `uv run engine` | `.env` |
| Dashboard | `src/dashboard/api.py` | `uv run dashboard` | `.env` |

`src/main.py` (~840 lines) orchestrates 8 parallel async loops and 30 WebSocket tasks (10 symbols × 3 timeframes). It contains: `_5min_scanner`, `_bounty_watcher`, `_continuous_signal_scanner`, `_learning_loop`, `_auto_train_loop`, `_accounting_sync_loop`, `_api_health_monitor_loop`, and position monitor.

---

## Cross-cutting Files

| File | Role |
|------|------|
| `src/constants.py` | **Single source of truth** for all numeric parameters, `MODEL_FEATURES` list, risk thresholds, CB defaults, symbol list |
| `src/paths.py` | **Centralized data paths** — `BRAIN_LOG`, `RUNTIME_STATE`, `MODEL_PATH`, `MODELS_DIR`, `META_STATS_PATH`, `BEST_PARAMS_PATH`, `ENGINE_HEARTBEAT`. Respects `SYSMHO_DATA_DIR` env var (defaults to `src/`). |
| `src/runtime_config.py` | IPC channel between processes via `src/runtime_state.json`. Exposes: `is_autonomous()`, `set_autonomous()`, `reset_circuit_breaker()`, `reset_daily_pnl()`, `get_sync_status()`, `set_last_scan_at()` |
| `src/runtime_state.json` | JSON file written at runtime — shared state between AI Engine and Dashboard. Not committed to git. |

**Rule**: Never hardcode thresholds that belong in `constants.py`. If a number appears more than once, it belongs there.

---

## Code Conventions

- **Classes**: PascalCase — `DatabaseRepository`, `ModelPredictor`, `CircuitBreaker`
- **Functions / methods**: snake_case — `evaluate_signal()`, `sync_portfolio_on_trade()`
- **Constants**: UPPER_SNAKE_CASE — `MODEL_FEATURES`, `CB_MAX_POSITIONS`
- **Logging**: prefix with `[MODULE]` tag — e.g. `[EXECUTOR]`, `[PREDICTOR]`, `[AUTONOMY]`
- **Error handling**: silent try/except in loops (log the error, continue the loop); raise in initialization paths
- **Async**: all DB and Binance calls are `async/await`. The engine is fully async (asyncio).

---

## Key Dependency Flow (text diagram)

```
.env
  └── config/settings.py
        └── DATABASE_URL → repository.py
        └── BINANCE_* → trader.py

src/constants.py  ←── imported by practically every module

collector/ (websocket, gap_filler)
  └── repository.py → PostgreSQL

analysis/ (indicators → features)
  └── repository.py (data fetch)
  └── constants.py (MODEL_FEATURES)

ai/ (predictor, trainer, meta_evaluator, self_learner)
  └── features.py → analysis/
  └── repository.py → PostgreSQL
  └── constants.py

risk/ (manager)
  └── constants.py

executor/ (trader, monitor, circuit_breaker)
  └── repository.py → PostgreSQL
  └── config/settings.py (Binance keys)
  └── constants.py

src/main.py  ←── imports from all of the above
src/dashboard/api.py ←── imports from deps.py (singletons: db, trader, risk, monitor)
```

**Collectors always use Binance mainnet** (public data, no sandbox). Only `trader.py` respects `BINANCE_TESTNET`.
