# AGENTS.md — src/dashboard/

> **Navigation:** `CLAUDE.md` (manifest) → `AGENTS.md` (skills index) → `src/AGENTS.md` (module architecture) → This file (API & frontend)
>
> **When to read:** Building or modifying API endpoints, authentication, frontend features, or dashboard integrations.
> **Loading strategy:** On-demand — loaded only when you need dashboard/API context (not preloaded).

---

## API

FastAPI application (`src/dashboard/api.py`) with `X-API-Key` middleware authentication.
- **Port**: 8000
- **Auth header**: `X-API-Key: <value>` — value defined in `.env` as `DASHBOARD_API_KEY`. Never expose this value in code or documentation.
- **Start command**: `uv run uvicorn src.dashboard.api:app --host 0.0.0.0 --port 8000`
- **Static assets**: Mounted at `/assets` — served from `src/dashboard/static/assets/`

---

## Routers

| Router file | Main Endpoints | Method |
|-------------|---------------|--------|
| `routes/system.py` | `/api/system/status`, `/api/system/last_scan`, `/api/data/freshness`, `/api/db/status`, `/api/system/sync_status`, `/api/logs` | GET |
| `routes/market.py` | `/api/market_data/{symbol}` | GET |
| `routes/signals.py` | `/api/pending_signals`, `/api/pending_signals/{id}/approve`, `/api/pending_signals/{id}/reject`, `/api/pending_signals/dismiss_all`, `/api/authorized_history` | GET / POST |
| `routes/positions.py` | `/api/positions`, `/api/positions/{id}/close` | GET / POST |
| `routes/portfolio.py` | `/api/balance`, `/api/stats`, `/api/trades/history`, `/api/portfolio/adjust_capital`, `/api/portfolio/reset_pnl` | GET / POST |
| `routes/autonomous.py` | `/api/autonomous/status`, `/api/autonomous/decisions`, `/api/autonomous/toggle`, `/api/autonomous/reset_cb` | GET / POST |
| `routes/testing.py` | `/api/test/inject_signal` | POST |

---

## Singletons (`deps.py`)

`deps.py` holds the global singleton instances shared across all routes:

| Instance | Type | Role |
|----------|------|------|
| `db` | `DatabaseRepository` | asyncpg pool — all DB queries go through this |
| `trader` | `TradeExecutor` | Binance order execution + balance queries |
| `risk` | `RiskManager` | Signal auditing and position sizing |
| `monitor` | `PositionMonitor` | Live position tracking and TP/SL checks |

Also exports `log_tactico()` — writes structured entries to the neural log.

---

## Frontend

**Technology**: Vanilla JS + CSS (no framework dependencies).
**Location**: `src/dashboard/static/`

| File | Size | Role |
|------|------|------|
| `static/index.html` | ~294 lines | HTML structure, lock screen overlay, autonomy modal |
| `static/assets/style.css` | ~772 lines | Glassmorphism dark theme, telemetry colors, animations |
| `static/assets/app.js` | ~1230 lines | Auth logic, polling engine, charts, signals, autonomy panel, daily PnL |

**Polling**: 14 independent intervals — each endpoint has its own refresh rate. The JS polls the API; there is no WebSocket between frontend and backend.

**Lock screen**: Shown on startup. Unlocked by entering `DASHBOARD_API_KEY`. The key is stored in `localStorage` once validated.

---

## Dashboard Badge Indicators

| Badge | Endpoint | Green condition |
|-------|----------|----------------|
| `LINK ACTIVE` | `/api/system/status` | Binance API responds (fetch_balance OK) |
| `DB ACTIVE` | `/api/db/status` | PostgreSQL responds (`SELECT 1`) |
| `DATA Xs` | `/api/data/freshness` | Last 5m candle < 5min 30s ago (FRESH) |
| `⏱ 4:34` | `/api/system/last_scan` | Countdown to next REGULAR scan |
| `SYNCING...` | `/api/system/sync_status` | Gap Filler running at startup |
| `MANUAL` / `AUTONOMOUS` / `CB ACTIVE` | `/api/autonomous/status` | Current operation mode |

**DATA thresholds**:
- Green `FRESH`: last candle < 5m 30s
- Orange `DELAY`: last candle 5m 30s – 15m
- Red `STALE`: last candle > 15m (real data problem)
