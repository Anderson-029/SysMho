---
name: sysmho-market
description: Real-time crypto market context — BTC/ETH trends, funding rates, RSI for all 10 assets and overheating alerts. Use when assessing current market conditions.
allowed-tools: Read Shell
---

Generate a market context snapshot for SysMho's 10 active assets.

## BTC condition (market leader)

Query the database (connection: `config/settings.py` → `DATABASE_URL`):

```sql
-- Last 4h candle for BTC
SELECT close, open,
       (close - open) / open * 100 AS pct_change
FROM market_data
WHERE symbol = 'BTC/USDT' AND timeframe = '4h'
ORDER BY open_time DESC
LIMIT 1;
```

Display: direction (▲ BULLISH / ▼ BEARISH), % change, price.

## 5m snapshot for all assets

```sql
SELECT symbol, close, open,
       (close - open) / open * 100 AS pct_change
FROM market_data
WHERE timeframe = '5m'
  AND symbol IN ('BTC/USDT','ETH/USDT','BNB/USDT','SOL/USDT','XRP/USDT',
                  'ADA/USDT','AVAX/USDT','LINK/USDT','DOT/USDT','POL/USDT')
  AND open_time = (
      SELECT MAX(open_time) FROM market_data m2
      WHERE m2.symbol = market_data.symbol AND m2.timeframe = '5m'
  )
ORDER BY symbol;
```

Show icon: 🟢 if pct_change > 0.2%, 🔴 if < -0.2%, ⚪ otherwise.

## Funding rates

```sql
SELECT symbol, funding_rate
FROM sentiment_data
WHERE symbol IN ('BTC/USDT','ETH/USDT','BNB/USDT','SOL/USDT','XRP/USDT',
                  'ADA/USDT','AVAX/USDT','LINK/USDT','DOT/USDT','POL/USDT')
ORDER BY symbol;
```

Show ⚠️ if `abs(funding_rate) > 0.001`, else ✅.

## Interpretation and alerts

Based on the data, generate automatic alerts:

- **BTC bearish on 4h**: BUY signals in altcoins carry higher risk — recommend caution or reducing `NOTIONAL_CAP_RATIO`
- **Funding rate > 0.1%**: market overheated in longs — avoid BUY on that asset
- **Funding rate < -0.1%**: excessive shorts — possible contrarian signal
- **Multiple assets in the red simultaneously**: possible market correction — consider pausing autonomous mode

## Executive summary

```
CRYPTO MARKET — [UTC TIME]
BTC 4h Trend: BULLISH/BEARISH
Assets in green: N/10
Anomalous funding rates: N assets
Recommendation: TRADE NORMAL / CAUTION / PAUSE
```
