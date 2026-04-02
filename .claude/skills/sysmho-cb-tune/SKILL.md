---
name: sysmho-cb-tune
description: Analiza historial de trades y sugiere umbrales óptimos del Circuit Breaker con evidencia estadística
user-invocable: true
allowed-tools: Bash, Read
---

Analiza el historial real de trades de SysMho y calcula los umbrales óptimos para el Circuit Breaker basándose en datos reales, no en valores arbitrarios.

## Análisis de rachas y patrones

```bash
cd "/home/anderson/Documentos/programas personales/SysMho"
source venv/bin/activate && PYTHONPATH=$(pwd) python3 -c "
import asyncio, asyncpg
async def main():
    conn = await asyncpg.connect(host='localhost', port=5432, user='postgres', password='ander123', database='sysmho')

    trades = await conn.fetch('''
        SELECT id, symbol, pnl, executed_at,
               CASE WHEN pnl > 0 THEN 1 ELSE 0 END as win
        FROM trades WHERE status='CLOSED'
        ORDER BY executed_at
    ''')

    if len(trades) < 10:
        print(f'Solo {len(trades)} trades. Necesitas más datos para calibrar el CB.')
        await conn.close()
        return

    # Rachas de pérdidas
    max_loss_streak = 0
    curr_streak = 0
    streaks = []
    for t in trades:
        if t['win'] == 0:
            curr_streak += 1
            max_loss_streak = max(max_loss_streak, curr_streak)
        else:
            if curr_streak > 0:
                streaks.append(curr_streak)
            curr_streak = 0

    # Pérdida diaria máxima histórica
    daily = await conn.fetch('''
        SELECT DATE(executed_at) as dia,
               SUM(pnl) as pnl_dia,
               COUNT(*) as trades_dia
        FROM trades WHERE status='CLOSED'
        GROUP BY dia ORDER BY pnl_dia
        LIMIT 5
    ''')

    # Trades por día máximo
    max_daily = await conn.fetchval('''
        SELECT MAX(cnt) FROM (
            SELECT COUNT(*) as cnt FROM trades
            WHERE status='CLOSED'
            GROUP BY DATE(executed_at)
        ) sub
    ''')

    print(f'Total trades analizados: {len(trades)}')
    print()
    print('=== RACHAS DE PÉRDIDAS ===')
    print(f'Racha máxima histórica: {max_loss_streak}')
    print(f'Rachas > 2: {sum(1 for s in streaks if s > 2)}')
    print(f'Rachas > 3: {sum(1 for s in streaks if s > 3)}')
    print()
    print('=== PEORES DÍAS ===')
    for d in daily:
        print(f'{d[\"dia\"]}: PnL={d[\"pnl_dia\"]:.2f} USDT ({d[\"trades_dia\"]} trades)')
    print()
    print(f'=== ACTIVIDAD DIARIA ===')
    print(f'Max trades en un día: {max_daily}')

    await conn.close()
asyncio.run(main())
" 2>&1
```

## Recomendaciones basadas en datos

Basándote en los resultados anteriores y los valores actuales del `.env`, calcula y recomienda:

Lee el `.env` actual:
```bash
grep "CB_" "/home/anderson/Documentos/programas personales/SysMho/.env"
```

Luego genera recomendaciones en este formato:

```
PARÁMETRO          ACTUAL    RECOMENDADO    RAZÓN
CB_MAX_CONSEC_LOSSES  3      X             La racha máxima histórica fue N, recomiendo N-1
CB_MAX_DAILY_TRADES   8      X             El día de mayor actividad tuvo N trades
CB_DAILY_LOSS_PCT     4%     X%            El peor día fue -X%, un límite de X%*0.8 es conservador
CB_WEEKLY_DRAWDOWN    8%     X%            Basado en la suma de los 5 peores días consecutivos
CB_MAX_POSITIONS      3      X             Mantener en 3 hasta tener más historial
```

Si hay menos de 50 trades: indica que los datos son insuficientes para una recomendación estadísticamente válida y muestra lo que hay como referencia provisional.
