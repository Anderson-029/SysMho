---
name: sysmho-deploy
description: Controlled restart — verifies open positions, stops processes, applies pending migrations, starts in order. Use when restarting SysMho safely.
allowed-tools: Read Shell
---

Orchestrate a safe and controlled restart of SysMho.

## Step 1 — Verify open positions

Query the database (connection: `config/settings.py` → `DATABASE_URL`):

```sql
SELECT COUNT(*) AS open_count FROM positions;

SELECT symbol, side, pnl_unrealized
FROM positions
ORDER BY symbol;
```

If there are open positions, **warn clearly** that stopping SysMho will leave them without SL/TP monitoring. Ask for explicit confirmation before continuing.

## Step 2 — Stop current processes

Instruct the user to stop the running processes:
- Stop the Dashboard: terminate the `uvicorn src.dashboard.api` process
- Wait ~1 second
- Stop the AI Engine: terminate the `python -m src.main` process
- Wait ~2 seconds before starting again

> On Linux/macOS: `pkill -f "uvicorn src.dashboard.api"` and `pkill -f "python.*src.main"`
> On Windows: use Task Manager or `Stop-Process` in PowerShell to find and kill the relevant Python processes.

## Step 3 — Check for pending migrations

List the SQL files in `src/database/` and compare with what is known to be applied. If there are unapplied migrations, warn and ask whether to apply them before starting. Use the `sysmho-migrate` skill for safe application.

## Step 4 — Clear the neural log (optional)

Ask whether to clear the log before starting:
- Clear `src/sysmho_brain.log` (truncate to empty) if the user wants a clean slate.

## Step 5 — Start in correct order

Run from the workspace root:

```bash
# 1. Dashboard first (background)
uv run uvicorn src.dashboard.api:app --host 0.0.0.0 --port 8000

# 2. AI Engine after (in a separate terminal or background)
uv run python -m src.main
```

Wait ~3 seconds after starting the dashboard before starting the engine.
Verify the dashboard is up: `curl -s -o /dev/null -w '%{http_code}' http://localhost:8000` should return 200.

## Step 6 — Verify startup

- Check that both processes are running
- Read the first 20 lines of `src/sysmho_brain.log` to confirm the Gap Filler started and WebSockets are connecting

## Final Report

```
SYSMHO v15.2.0 DEPLOY — [DATE TIME]
─────────────────────────────────────
Positions preserved: N
Dashboard: ✅ running (port 8000)
Engine: ✅ running
Gap Filler: starting (check logs)
URL: http://localhost:8000
```
