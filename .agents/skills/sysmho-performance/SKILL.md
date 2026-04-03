---
name: sysmho-performance
description: Real performance analysis — KPIs, win rate, PnL, best assets and MetaEvaluator calibration. Use when evaluating trading performance.
allowed-tools: Read Shell
---

Generate a complete performance report for SysMho based on real database data.

## Global metrics

Query the database (connection: `config/settings.py` → `DATABASE_URL`):

```sql
-- Global summary
SELECT COUNT(*) AS total,
       COUNT(*) FILTER (WHERE pnl > 0) AS wins,
       COUNT(*) FILTER (WHERE pnl < 0) AS losses,
       ROUND(COALESCE(SUM(pnl), 0)::numeric, 2) AS total_pnl,
       ROUND(AVG(pnl)::numeric, 4) AS avg_pnl,
       ROUND(MAX(pnl)::numeric, 2) AS best_trade,
       ROUND(MIN(pnl)::numeric, 2) AS worst_trade
FROM trades
WHERE status = 'CLOSED';

-- By asset
SELECT symbol,
       COUNT(*) AS trades,
       COUNT(*) FILTER (WHERE pnl > 0) AS wins,
       ROUND(SUM(pnl)::numeric, 2) AS pnl
FROM trades
WHERE status = 'CLOSED'
GROUP BY symbol
ORDER BY pnl DESC;

-- By UTC hour
SELECT EXTRACT(HOUR FROM executed_at) AS hour,
       COUNT(*) AS trades,
       COUNT(*) FILTER (WHERE pnl > 0) AS wins,
       ROUND(SUM(pnl)::numeric, 2) AS pnl
FROM trades
WHERE status = 'CLOSED'
GROUP BY hour
ORDER BY hour;

-- BOUNTY vs REGULAR
SELECT pa.alert_category,
       COUNT(*) AS trades,
       COUNT(*) FILTER (WHERE t.pnl > 0) AS wins,
       ROUND(SUM(t.pnl)::numeric, 2) AS pnl
FROM trades t
JOIN pending_approvals pa ON t.signal_id = pa.id
WHERE t.status = 'CLOSED'
GROUP BY pa.alert_category;
```

Calculate and display win rate per group. For hourly data, show a simple bar visualization (e.g. `█` per 10% win rate).

## MetaEvaluator calibration

```sql
SELECT ad.decision,
       COUNT(*) AS total,
       ROUND(AVG(ad.meta_score)::numeric, 4) AS avg_meta_score,
       COUNT(*) FILTER (WHERE t.pnl > 0) AS wins_after_approval
FROM autonomous_decisions ad
LEFT JOIN trades t
    ON ad.symbol = t.symbol
    AND t.executed_at > ad.created_at
    AND t.executed_at < ad.created_at + INTERVAL '1 hour'
    AND t.status = 'CLOSED'
WHERE ad.decision = 'APPROVED'
GROUP BY ad.decision, ad.meta_score
ORDER BY ad.meta_score;
```

## Automatic recommendations

Based on results:
- If global Win Rate < 50%: suggest reviewing `META_SCORE_THRESHOLD` or `NORMAL_MIN_CONFIDENCE` in `constants.py`
- If any hour has WR < 40% with > 10 trades: suggest restricting trading in those hours
- If BOUNTY has significantly higher WR than REGULAR: suggest raising `HIGH_CONVICTION_THRESHOLD`
- If any asset consistently loses: suggest reviewing its features or temporarily excluding it
