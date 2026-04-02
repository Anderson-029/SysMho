---
name: sysmho-performance
description: Análisis de rendimiento real de SysMho — KPIs, win rate, PnL, mejores activos y calibración del MetaEvaluador
user-invocable: true
allowed-tools: Bash, Read
---

Genera un reporte completo de rendimiento de SysMho basado en datos reales de la BD.

## Métricas globales

```bash
cd "/home/anderson/Documentos/programas personales/SysMho"
source venv/bin/activate && PYTHONPATH=$(pwd) python3 -c "
import asyncio, asyncpg
async def main():
    conn = await asyncpg.connect(host='localhost', port=5432, user='postgres', password='ander123', database='sysmho')

    # Global
    g = await conn.fetchrow('''
        SELECT COUNT(*) as total,
               COUNT(*) FILTER (WHERE pnl > 0) as wins,
               COUNT(*) FILTER (WHERE pnl < 0) as losses,
               ROUND(COALESCE(SUM(pnl),0)::numeric,2) as total_pnl,
               ROUND(AVG(pnl)::numeric,4) as avg_pnl,
               ROUND(MAX(pnl)::numeric,2) as best_trade,
               ROUND(MIN(pnl)::numeric,2) as worst_trade
        FROM trades WHERE status='CLOSED'
    ''')
    print('=== GLOBAL ===')
    wr = (g['wins']/g['total']*100) if g['total'] > 0 else 0
    print(f'Trades: {g[\"total\"]} | Win Rate: {wr:.1f}% | PnL Total: \${g[\"total_pnl\"]}')
    print(f'Avg PnL: \${g[\"avg_pnl\"]} | Mejor: \${g[\"best_trade\"]} | Peor: \${g[\"worst_trade\"]}')

    # Por símbolo
    by_sym = await conn.fetch('''
        SELECT symbol,
               COUNT(*) as trades,
               COUNT(*) FILTER (WHERE pnl > 0) as wins,
               ROUND(SUM(pnl)::numeric,2) as pnl
        FROM trades WHERE status='CLOSED'
        GROUP BY symbol ORDER BY pnl DESC
    ''')
    print('\n=== POR ACTIVO ===')
    for r in by_sym:
        wr2 = (r['wins']/r['trades']*100) if r['trades'] > 0 else 0
        print(f'{r[\"symbol\"]}: {r[\"trades\"]} trades | WR {wr2:.0f}% | PnL \${r[\"pnl\"]}')

    # Por hora del día
    by_hour = await conn.fetch('''
        SELECT EXTRACT(HOUR FROM executed_at) as hora,
               COUNT(*) as trades,
               COUNT(*) FILTER (WHERE pnl > 0) as wins,
               ROUND(SUM(pnl)::numeric,2) as pnl
        FROM trades WHERE status='CLOSED'
        GROUP BY hora ORDER BY hora
    ''')
    print('\n=== POR HORA UTC ===')
    for r in by_hour:
        wr3 = (r['wins']/r['trades']*100) if r['trades'] > 0 else 0
        bar = '█' * int(wr3/10)
        print(f'{int(r[\"hora\"]):02d}h: {bar} {wr3:.0f}% ({r[\"trades\"]} trades)')

    # BOUNTY vs REGULAR
    by_cat = await conn.fetch('''
        SELECT pa.alert_category,
               COUNT(*) as trades,
               COUNT(*) FILTER (WHERE t.pnl > 0) as wins,
               ROUND(SUM(t.pnl)::numeric,2) as pnl
        FROM trades t
        JOIN pending_approvals pa ON t.signal_id = pa.id
        WHERE t.status='CLOSED'
        GROUP BY pa.alert_category
    ''')
    if by_cat:
        print('\n=== BOUNTY vs REGULAR ===')
        for r in by_cat:
            wr4 = (r['wins']/r['trades']*100) if r['trades'] > 0 else 0
            print(f'{r[\"alert_category\"]}: WR {wr4:.0f}% | PnL \${r[\"pnl\"]} ({r[\"trades\"]} trades)')

    await conn.close()
asyncio.run(main())
" 2>&1
```

## Calibración del MetaEvaluador

```bash
cd "/home/anderson/Documentos/programas personales/SysMho"
source venv/bin/activate && PYTHONPATH=$(pwd) python3 -c "
import asyncio, asyncpg
async def main():
    conn = await asyncpg.connect(host='localhost', port=5432, user='postgres', password='ander123', database='sysmho')
    decisions = await conn.fetch('''
        SELECT ad.decision, ad.meta_score,
               COUNT(*) as total,
               COUNT(*) FILTER (WHERE t.pnl > 0) as wins
        FROM autonomous_decisions ad
        LEFT JOIN trades t ON ad.symbol = t.symbol
            AND t.executed_at > ad.created_at
            AND t.executed_at < ad.created_at + INTERVAL '1 hour'
            AND t.status = 'CLOSED'
        WHERE ad.decision = 'APPROVED'
        GROUP BY ad.decision, ad.meta_score
        ORDER BY ad.meta_score
    ''')
    if decisions:
        print('Meta-score promedio en APPROVED:', sum(float(d['meta_score']) for d in decisions)/len(decisions))
    await conn.close()
asyncio.run(main())
" 2>&1
```

## Recomendaciones automáticas

Basándote en los resultados:
- Si Win Rate global < 50%: sugiere revisar `META_SCORE_THRESHOLD` o `NORMAL_MIN_CONFIDENCE`
- Si hay horas con WR < 40% y > 10 trades: sugiere restringir operaciones en esas horas
- Si BOUNTY tiene WR muy superior a REGULAR: sugiere subir `HIGH_CONVICTION_THRESHOLD`
- Si algún símbolo pierde consistentemente: sugiere revisar sus features o excluirlo temporalmente
