---
name: sysmho-market
description: Contexto de mercado cripto en tiempo real — tendencias BTC/ETH, funding rates, RSI de los 10 activos y alertas de sobrecalentamiento
user-invocable: true
allowed-tools: Bash, Read
---

Genera un snapshot del contexto de mercado actual para los 10 activos de SysMho.

## Condición de BTC (líder del mercado)

```bash
cd "/home/anderson/Documentos/programas personales/SysMho"
source venv/bin/activate && PYTHONPATH=$(pwd) python3 -c "
import asyncio, asyncpg
async def main():
    conn = await asyncpg.connect(host='localhost', port=5432, user='postgres', password='ander123', database='sysmho')

    # Última vela 4h de BTC
    btc_4h = await conn.fetchrow('''
        SELECT close, open,
               (close - open) / open * 100 as pct_change
        FROM market_data
        WHERE symbol='BTC/USDT' AND timeframe='4h'
        ORDER BY open_time DESC LIMIT 1
    ''')
    if btc_4h:
        direction = '▲ ALCISTA' if btc_4h['pct_change'] > 0 else '▼ BAJISTA'
        print(f'BTC 4h: {direction} ({btc_4h[\"pct_change\"]:+.2f}%) | Precio: {btc_4h[\"close\"]:,.0f}')

    # RSI y tendencia de todos los activos en 5m
    symbols = ['BTC/USDT','ETH/USDT','BNB/USDT','SOL/USDT','XRP/USDT',
               'ADA/USDT','AVAX/USDT','LINK/USDT','DOT/USDT','POL/USDT']

    print('\n=== SNAPSHOT 5m ===')
    for sym in symbols:
        row = await conn.fetchrow('''
            SELECT close, open,
                   (close - open) / open * 100 as pct_change
            FROM market_data
            WHERE symbol=\$1 AND timeframe='5m'
            ORDER BY open_time DESC LIMIT 1
        ''', sym)
        if row:
            icon = '🟢' if row['pct_change'] > 0.2 else ('🔴' if row['pct_change'] < -0.2 else '⚪')
            print(f'{icon} {sym}: {row[\"close\"]:>12,.4f} ({row[\"pct_change\"]:+.2f}%)')

    # Funding rates
    print('\n=== FUNDING RATES ===')
    rates = await conn.fetch('''
        SELECT symbol, funding_rate
        FROM sentiment_data
        WHERE symbol = ANY(\$1)
        ORDER BY symbol
    ''', symbols)
    for r in rates:
        fr = float(r['funding_rate'] or 0)
        icon = '⚠️' if abs(fr) > 0.001 else '✅'
        print(f'{icon} {r[\"symbol\"]}: {fr:.4%}')

    await conn.close()
asyncio.run(main())
" 2>&1
```

## Interpretación y alertas

Basándote en los datos, genera alertas automáticas:

- **BTC bajista en 4h**: señales BUY en altcoins tienen mayor riesgo — recomendar cautela o reducir `NOTIONAL_CAP_RATIO`
- **Funding rate > 0.1%**: mercado sobrecalentado en longs — evitar BUY en ese activo
- **Funding rate < -0.1%**: shorts excesivos — contrarian signal posible
- **Múltiples activos en rojo simultáneo**: posible corrección de mercado — considerar pausar modo autónomo

## Resumen ejecutivo

```
MERCADO CRIPTO — [HORA UTC]
BTC Tendencia 4h: ALCISTA/BAJISTA
Activos en verde: N/10
Funding rates anómalos: N activos
Recomendación: OPERAR NORMAL / CAUTELA / PAUSAR
```
