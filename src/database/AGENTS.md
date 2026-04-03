# AGENTS.md — src/database/

> Parent context: `src/AGENTS.md` → `AGENTS.md` (root)

---

## Connection

Always connect via `config/settings.py` → `DATABASE_URL` (loaded from `.env`).

```python
# In settings.py — the only place credentials are loaded:
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
```

`repository.py` creates an asyncpg connection pool (min=5, max=50) at startup. **Never** pass inline credentials in any skill, script, or command. All DB access goes through `DatabaseRepository` or via psql using the `DATABASE_URL` from the environment.

---

## Tables

| Table | Main Columns | Role |
|-------|-------------|------|
| `market_data` | `symbol`, `timeframe`, `open_time`, `open`, `high`, `low`, `close`, `volume` | OHLCV candles — primary data store |
| `positions` | `symbol`, `side`, `quantity`, `entry_price`, `sl_price`, `tp_price`, `pnl_unrealized`, `invested_usdt` | Open positions tracked in real-time |
| `trades` | `symbol`, `side`, `status`, `pnl`, `entry_price`, `exit_price`, `executed_at`, `signal_id` | Full trade history (OPEN / CLOSED) |
| `pending_approvals` | `symbol`, `side`, `win_probability`, `alert_category`, `score`, `status`, `created_at` | Signals awaiting decision (PENDING / APPROVED / REJECTED / DISMISSED) |
| `autonomous_decisions` | `symbol`, `decision`, `meta_score`, `reason`, `created_at` | Log of MetaEvaluator approve/reject actions |
| `portfolio` | `total_balance`, `available_balance`, `in_positions`, `total_pnl`, `recorded_at` | Portfolio state snapshots |
| `sentiment_data` | `symbol`, `funding_rate`, `open_interest`, `obi_20`, `updated_at` | Funding rate + order book imbalance |
| `model_performance` | `model_name`, `symbol`, `accuracy`, `precision_score`, `recall`, `total_predictions`, `created_at` | Training metrics per model version |
| `risk_log` | `symbol`, `reason`, `action`, `created_at` | Risk manager rejection log |
| `meta_stats` | `symbol`, `win_rate`, `win_rate_by_hour`, `confidence_calibration`, `updated_at` | SelfLearner statistics (also stored in `src/ai/models/meta_stats.json`) |

> Note: The legacy table `sentiment_data_ts` may also exist as a time-series variant. Check `schema.sql` for the current DDL.

---

## Frequent Queries

### Open positions

```sql
SELECT symbol, side, quantity, entry_price, invested_usdt, pnl_unrealized
FROM positions
ORDER BY symbol;
```

### Latest portfolio snapshot

```sql
SELECT total_balance, available_balance, in_positions, total_pnl, recorded_at
FROM portfolio
ORDER BY recorded_at DESC
LIMIT 1;
```

### Today's closed trades (respecting CB reset)

```sql
SELECT COUNT(*) AS trades,
       COUNT(*) FILTER (WHERE pnl > 0) AS winners,
       ROUND(COALESCE(SUM(pnl), 0)::numeric, 2) AS pnl_realized
FROM trades
WHERE status = 'CLOSED'
  AND executed_at >= CURRENT_DATE;
```

### Pending signals

```sql
SELECT id, symbol, side, win_probability, alert_category, score, created_at
FROM pending_approvals
WHERE status = 'PENDING'
ORDER BY alert_category DESC, score DESC;
```

### Last autonomous decisions

```sql
SELECT symbol, decision, meta_score, reason, created_at
FROM autonomous_decisions
ORDER BY created_at DESC
LIMIT 10;
```

### Last telemetry / data freshness

```sql
SELECT symbol, timeframe, MAX(open_time) AS last_candle,
       EXTRACT(EPOCH FROM (NOW() - MAX(open_time))) / 60 AS minutes_ago
FROM market_data
WHERE timeframe = '5m'
GROUP BY symbol, timeframe
ORDER BY minutes_ago DESC;
```

---

## Migrations

**Convention**: `migration_vX_Y_Z.sql` in `src/database/`.

| File | What it adds |
|------|-------------|
| `migration_v14_9_0.sql` | `alert_category` and `score` columns to `pending_approvals` |
| `migration_v15_0_0.sql` | Marks v2 models deprecated; adds index on `model_performance.model_name` |
| `migration_v15_2_0.sql` | Creates `autonomous_decisions` and `meta_stats` tables |

**How to apply**: Use the `sysmho-migrate` skill (`.claude/skills/sysmho-migrate/SKILL.md`) which guides safe application and verification. To apply manually: `psql $DATABASE_URL -f src/database/migration_vX_Y_Z.sql`.
