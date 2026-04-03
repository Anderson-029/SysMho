---
name: sysmho
description: Master diagnostic panel — runs a full system health check in one command. Use when you need a quick overview of all SysMho subsystems.
allowed-tools: Read Shell
---

You are the master control panel for SysMho v15.2.0. Run this full diagnostic in order and present everything as a structured visual report.

---

## BLOCK 1 — PROCESSES AND SYSTEM

Check if the following processes are running:
- Dashboard (FastAPI/uvicorn): look for `uvicorn` or `src.dashboard.api` in the process list
- AI Engine (main.py): look for `src.main` in the process list
- PostgreSQL: verify the DB is reachable

Report:
- Dashboard: ✅ running / ❌ stopped
- Motor: ✅ running / ❌ stopped
- PostgreSQL: ✅ available / ❌ down

---

## BLOCK 2 — RUNTIME STATE

Read `src/runtime_state.json` and display:
- Mode: **AUTONOMOUS** or **MANUAL**
- Circuit Breaker: active or OK
- PnL reset: when was the last reset
- Sync status: idle or syncing

---

## BLOCK 3 — RECENT TELEMETRY

Read the last 30 lines of `src/sysmho_brain.log`.

Group and show only what matters:
- ❌ Errors from the last few hours
- 🛑 Circuit Breaker: if triggered
- 🤖 Last autonomous decisions (APPROVED/REJECTED)
- ✅ Last order executions

---

## BLOCK 4 — TODAY'S METRICS (from the DB)

Query the database (connection: `config/settings.py` → `DATABASE_URL`):

```sql
-- Today's trades
SELECT COUNT(*) AS trades_today,
       COUNT(*) FILTER (WHERE pnl > 0) AS winners,
       ROUND(COALESCE(SUM(pnl), 0)::numeric, 2) AS pnl_realized
FROM trades
WHERE status = 'CLOSED'
  AND executed_at >= CURRENT_DATE;

-- Open positions
SELECT COUNT(*) AS open_count,
       ROUND(COALESCE(SUM(pnl_unrealized), 0)::numeric, 2) AS floating_pnl
FROM positions;

-- Last 3 autonomous decisions
SELECT symbol, decision, meta_score, created_at
FROM autonomous_decisions
ORDER BY created_at DESC
LIMIT 3;
```

---

## BLOCK 5 — PENDING SIGNALS

Query the database (connection: `config/settings.py` → `DATABASE_URL`):

```sql
SELECT symbol, side, win_probability, alert_category, score, created_at
FROM pending_approvals
WHERE status = 'PENDING'
ORDER BY score DESC;
```

Show each signal with: category, symbol, direction, confidence, score, time remaining (signals expire after 5 minutes).

---

## FINAL REPORT FORMAT

Present everything as a clean command panel:

```
╔══════════════════════════════════════════════════╗
║         SYSMHO v15.2.0 — Master Panel            ║
╠══════════════════════════════════════════════════╣
║ Dashboard: ✅  Engine: ✅  DB: ✅                 ║
║ Mode: AUTONOMOUS  CB: OK  Sync: idle             ║
╠══════════════════════════════════════════════════╣
║ TODAY: X trades | X winners | PnL: $X.XX        ║
║ Open: X positions | Floating: $X.XX             ║
╠══════════════════════════════════════════════════╣
║ PENDING SIGNALS: X                               ║
║  ...                                             ║
╠══════════════════════════════════════════════════╣
║ LAST RELEVANT EVENTS                             ║
║  ...                                             ║
╚══════════════════════════════════════════════════╝
```

If any block fails (process down, DB not responding), mark it clearly with ❌ and continue with the remaining blocks.
