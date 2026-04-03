---
name: sysmho-audit
description: Full integrity audit — verifies coherence between local DB, Binance and system state. Use when suspecting data mismatches or desynchronization.
allowed-tools: Read Shell
---

Run a complete integrity audit of SysMho. Detect inconsistencies between the local DB and the real system state.

## CHECK 1 — Position consistency

Query the database (connection: `config/settings.py` → `DATABASE_URL`):

```sql
SELECT symbol, side, quantity, entry_price, invested_usdt, pnl_unrealized
FROM positions
ORDER BY symbol;
```

Report: number of positions found, and their details.

## CHECK 2 — Portfolio consistency

```sql
-- Latest portfolio snapshot
SELECT total_balance, available_balance, in_positions, recorded_at
FROM portfolio
ORDER BY recorded_at DESC
LIMIT 1;

-- Real sum of open positions
SELECT COALESCE(SUM(invested_usdt), 0) AS real_margin_in_use
FROM positions;
```

Compare `portfolio.in_positions` vs `SUM(positions.invested_usdt)`. Report: ✅ OK if difference < 0.10, ❌ INCONSISTENT otherwise (with the difference).

## CHECK 3 — Trades in invalid state

```sql
-- OPEN trades without a corresponding position
SELECT t.id, t.symbol, t.side
FROM trades t
LEFT JOIN positions p ON t.symbol = p.symbol
WHERE t.status = 'OPEN'
  AND p.symbol IS NULL;

-- Stale pending signals (older than 10 minutes)
SELECT id, symbol, created_at
FROM pending_approvals
WHERE status = 'PENDING'
  AND created_at < NOW() - INTERVAL '10 minutes';
```

Report: OPEN trades without a position: N ✅/❌ | Stale PENDING signals: N ✅/⚠️

## CHECK 4 — Runtime health

Read `src/runtime_state.json` and verify:
- The file exists and is valid JSON
- Timestamps (reset_at fields) are coherent (not in the future)
- `sync_status` is not stuck at `syncing` after startup

## CHECK 5 — Recent error log

Read `src/sysmho_brain.log` and search for lines containing ERROR, Exception, Traceback, or ❌ in the last section. Show the most recent 20 such lines.

## Final Report

```
SYSMHO AUDIT — [DATE]
─────────────────────────────────────
Positions DB:         ✅/❌ N found
Portfolio consistency:✅/❌ difference $X
Orphan trades:        ✅/❌
Stale signals:        ✅/⚠️
Runtime state:        ✅/❌
Recent errors:        ✅/❌ N errors

VERDICT: SYSTEM INTACT / REVIEW ITEMS ❌
```
