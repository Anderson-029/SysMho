# SysMho — Neural Combat Financial System

> Autonomous crypto trading bot on Binance Futures powered by XGBoost AI.
> Version: 15.2.0 | Status: Operational

## What is SysMho?

SysMho is an algorithmic trading system for perpetual crypto futures on Binance. It combines multi-timeframe technical analysis, swarm intelligence across 10 assets, an XGBoost model trained on 27 features, strict mathematical risk control, and an autonomous decision engine with continuous learning.

**Two operating modes:**
- **Manual**: Every signal requires human approval via the dashboard (Human-in-the-Loop).
- **Autonomous**: MetaEvaluator scores each signal statistically and decides automatically. Circuit Breaker acts as safety net.

**Portfolio**: BTC, ETH, BNB, SOL, XRP, ADA, AVAX, LINK, DOT, POL — all /USDT perpetual futures.
**Timeframes**: 5m (primary prediction) + 1h, 4h (macro context).

## Quick Start

### Prerequisites

- Python 3.12+
- PostgreSQL (local, database `sysmho`)
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

### Setup

```bash
# Clone and enter the repo
git clone <repo-url> && cd SysMho

# Copy environment file and fill in your keys
cp .env.example .env

# Install dependencies (pick one)
uv sync           # recommended — manages venv automatically
pip install -r requirements.txt  # fallback
```

### Configure `.env`

| Variable | Required | Description |
|----------|----------|-------------|
| `BINANCE_API_KEY` | Yes | Binance Futures API key |
| `BINANCE_SECRET_KEY` | Yes | Binance Futures secret |
| `BINANCE_TESTNET` | Yes | `True` for testnet, `False` for mainnet |
| `DB_HOST` | No | Default: `localhost` |
| `DB_PORT` | No | Default: `5432` |
| `DB_USER` | No | Default: `postgres` |
| `DB_PASSWORD` | No | Default: `postgres` |
| `DB_NAME` | No | Default: `sysmho` |
| `DASHBOARD_API_KEY` | Yes | API key for dashboard authentication |

### Run

```bash
# Option A: Use the startup script
bash start_sysmho.sh

# Option B: Start manually (two terminals)
uv run uvicorn src.dashboard.api:app --host 0.0.0.0 --port 8000   # Terminal 1: Dashboard
uv run python -m src.main                                          # Terminal 2: AI Engine
```

Dashboard: http://localhost:8000 (authenticate with your `DASHBOARD_API_KEY`).

## Architecture

```
Binance (real market data via WebSocket + REST)
    ↓
GapFiller (fills historical gaps on startup)
    ↓
PostgreSQL (~6.7M candles, 10 tables)
    ↓
FeatureEngineer (27 normalized features)
    ↓
XGBoost v3 (SELL / WAIT / BUY)
    ↓
RiskManager (position sizing, SL/TP, exposure limits)
    ↓
┌─────────────────┬──────────────────────┐
│ Manual mode     │ Autonomous mode      │
│ Human approves  │ CircuitBreaker check │
│ via dashboard   │ MetaEvaluator score  │
└────────┬────────┴──────────┬───────────┘
         ↓                   ↓
    TradeExecutor → Binance (testnet or mainnet)
         ↓
    PositionMonitor (1s loop: PnL, SL/TP, sync)
         ↓
    SelfLearner → meta_stats.json (continuous improvement)
```

**Two independent processes** communicate via PostgreSQL (data) and `src/runtime_state.json` (IPC control):
- **AI Engine** (`uv run python -m src.main`) — data collection, prediction, execution, monitoring
- **Dashboard** (`uv run uvicorn src.dashboard.api:app`) — REST API + web frontend

## Training the Model

```bash
# Train with existing hyperparameters
uv run python -m src.ai.trainer --symbol ALL --timeframe 5m

# Retrain with Bayesian optimization (Optuna, ~30 min)
uv run python -m src.ai.trainer --symbol ALL --timeframe 5m --tune --trials 50
```

If you change the feature set (`MODEL_FEATURES` in `src/constants.py`), delete the old model first:
```bash
rm src/ai/models/xgboost_v1.joblib
```

## Running Tests

```bash
uv run pytest          # full suite (56 tests)
uv run pytest -x -v    # stop on first failure, verbose
```

## Autonomous Mode

Controlled via the dashboard's Autonomy panel (no restart needed):

| Component | Role |
|-----------|------|
| **MetaEvaluator** | 5-component statistical filter (win rate, hourly WR, confidence calibration, loss streak, base confidence). Approves if `meta_score >= 0.52`. |
| **Circuit Breaker** | 5 hard stops: max positions (3), max daily trades (8), max consecutive losses (3), daily loss limit (4%), weekly drawdown limit (8%). All configurable via `.env`. |
| **SelfLearner** | Updates `meta_stats.json` per closed trade. Foundation for future XGBoost meta-model (Phase 2, needs 200+ trades). |

## Key Configuration (`src/constants.py`)

| Parameter | Value | Description |
|-----------|-------|-------------|
| `LABEL_THRESHOLD` | 0.007 | Min movement (0.7%) to label BUY/SELL |
| `NORMAL_MIN_CONFIDENCE` | 0.38 | Min signal confidence |
| `NORMAL_INERTIA_THRESHOLD` | 0.72 | Veto if WAIT > 72% |
| `HIGH_CONVICTION_THRESHOLD` | 0.55 | BOUNTY signal threshold |
| `NORMAL_RISK_PER_TRADE` | 0.02 | 2% capital risk per trade |
| `NORMAL_ATR_SL` / `NORMAL_ATR_TP` | 1.5 / 3.0 | SL at 1.5x ATR, TP at 3.0x ATR |
| `NOTIONAL_CAP_RATIO` | 0.12 | Max 12% capital per trade |
| `EXPOSURE_LIMIT_RATIO` | 0.50 | Block if total exposure > 50% |
| `META_SCORE_THRESHOLD` | 0.52 | MetaEvaluator approval threshold |

## Migrating to Mainnet

1. Create Binance Futures API keys with trading permissions
2. Update `.env`: set real keys and `BINANCE_TESTNET=False`
3. Restart SysMho

Data collectors already use Binance mainnet (public endpoints). Only `trader.py` respects `BINANCE_TESTNET`.

## Agent Setup

This project uses [Agent Skills](https://agentskills.io) for AI-assisted development. See `AGENTS.md` for the universal agent router, skills index, and maintenance protocol.

## Version History

### v15.2.0 (2026-03-30) — Current stable
- Autonomous mode: MetaEvaluator with 5 statistical components
- Circuit Breaker: 5 hard stops, configurable via env vars
- SelfLearner: continuous learning from closed trades
- Gap Filler: auto-fills historical gaps on startup
- Runtime IPC channel via `runtime_state.json`
- Persistent daily PnL tracking
- Dashboard offline detection with auto-recovery
- Color-coded telemetry (orange: CB, yellow: autonomy, green: execution)

### v15.1.0 (2026-03-29)
- End-to-end execution verified on Binance testnet
- Real-time order telemetry in brain log
- Vectorized backtest with real Binance fees (WR 58.2%, PF 2.12x)

### v15.0.0 (2026-03-29)
- ML pipeline redesign: 27 clean features (from 65), all normalized
- TimeSeriesSplit 5-fold validation
- Balanced class weights
- Swarm Intelligence with `swarm_bull_ratio` and temporal lag fix

### v14.9.0 (2026-03-28)
- REGULAR + BOUNTY alert system with composite scoring
- Automatic signal timeout (5 min)

### v14.8.5 (2026-03-26)
- Critical fix: SHORT TP calculation
- 56/56 tests green
- Optuna retraining (50 trials, log-loss 0.2893)

## Roadmap

1. Resolve Binance account verification for mainnet trading
2. Accumulate 200+ trades in autonomous testnet mode for meta-model training
3. Calibrate Circuit Breaker thresholds based on testnet results
4. Train XGBoost meta-model on `meta_stats.json` (Phase 2 autonomy)
5. Implement adaptive ATR-based labeling to replace fixed 0.7% threshold
6. Add per-class precision metrics (BUY/SELL) to model evaluation
