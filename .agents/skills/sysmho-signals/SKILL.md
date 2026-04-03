---
name: sysmho-signals
description: Tactical signals view — pending signals, recent history, approval rate and decision context. Use when reviewing trading signal activity.
allowed-tools: Read Shell
---

Generate a complete tactical view of SysMho signals.

## Pending signals right now

Query the database (connection: `config/settings.py` → `DATABASE_URL`):

```sql
SELECT id, symbol, side, win_probability, alert_category, score,
       stop_loss, take_profit, quantity, created_at
FROM pending_approvals
WHERE status = 'PENDING'
ORDER BY alert_category DESC, score DESC;
```

For each signal, calculate and show:
- Category (BOUNTY or REGULAR), symbol, direction
- Confidence (`win_probability`), score
- SL, TP, quantity
- Time remaining (signals expire after 300 seconds / 5 minutes)
- Signal ID

If no results: "No pending signals at this time."

## Recent history (last 24h)

```sql
SELECT symbol, side, status, win_probability, alert_category, score, created_at
FROM pending_approvals
WHERE created_at >= NOW() - INTERVAL '24 hours'
ORDER BY created_at DESC
LIMIT 20;
```

Show each row with a status icon: APPROVED ✅ | REJECTED ❌ | DISMISSED ⏱️ | PENDING ⏳

Then show approval rates:

```sql
SELECT
    COUNT(*) AS total,
    COUNT(*) FILTER (WHERE status = 'APPROVED') AS approved,
    COUNT(*) FILTER (WHERE status = 'REJECTED') AS rejected,
    COUNT(*) FILTER (WHERE status = 'DISMISSED') AS dismissed
FROM pending_approvals
WHERE created_at >= NOW() - INTERVAL '24 hours';
```

## Current mode context

Read `src/runtime_state.json` and show whether the system is in MANUAL or AUTONOMOUS mode — this changes how to interpret pending signals:
- **MANUAL**: Signals wait for human approval in the dashboard.
- **AUTONOMOUS**: MetaEvaluator decides in milliseconds — pending signals are rare.
