---
name: sysmho-cb-tune
description: Analyzes trade history and suggests optimal Circuit Breaker thresholds with statistical evidence. Use when calibrating CB parameters.
allowed-tools: Read Shell
---

Analyze the real trade history of SysMho and calculate optimal thresholds for the Circuit Breaker based on real data, not arbitrary values.

## Loss streak and pattern analysis

Query the database (connection: `config/settings.py` → `DATABASE_URL`):

```sql
-- All closed trades in chronological order
SELECT id, symbol, pnl, executed_at,
       CASE WHEN pnl > 0 THEN 1 ELSE 0 END AS win
FROM trades
WHERE status = 'CLOSED'
ORDER BY executed_at;
```

If fewer than 10 trades: report "Only N trades. You need more data to calibrate the CB."

From the results, calculate:
- Maximum historical loss streak (consecutive losses)
- Distribution of streaks (how many streaks > 2, > 3)

```sql
-- 5 worst days by PnL
SELECT DATE(executed_at) AS day,
       SUM(pnl) AS pnl_day,
       COUNT(*) AS trades_day
FROM trades
WHERE status = 'CLOSED'
GROUP BY day
ORDER BY pnl_day
LIMIT 5;

-- Maximum trades in a single day
SELECT MAX(cnt) AS max_daily_trades
FROM (
    SELECT COUNT(*) AS cnt
    FROM trades
    WHERE status = 'CLOSED'
    GROUP BY DATE(executed_at)
) sub;
```

## Recommendations based on data

Read `src/constants.py` to see current CB default values (`CB_MAX_CONSEC_LOSSES`, `CB_MAX_DAILY_TRADES`, `CB_DAILY_LOSS_PCT`, `CB_WEEKLY_DRAWDOWN_PCT`, `CB_MAX_POSITIONS`).

Also check `.env` for any overrides of CB parameters.

Generate recommendations in this format:

```
PARAMETER               CURRENT    RECOMMENDED    REASON
CB_MAX_CONSEC_LOSSES      3         X             Historical max streak was N, recommend N-1
CB_MAX_DAILY_TRADES       8         X             Highest activity day had N trades
CB_DAILY_LOSS_PCT         4%        X%            Worst day was -X%, limit of X%*0.8 is conservative
CB_WEEKLY_DRAWDOWN_PCT    8%        X%            Based on sum of 5 worst consecutive days
CB_MAX_POSITIONS          3         X             Keep at 3 until more history available
```

If fewer than 50 trades: indicate that data is insufficient for a statistically valid recommendation and show what is available as a provisional reference.
