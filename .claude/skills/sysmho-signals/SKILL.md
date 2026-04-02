---
name: sysmho-signals
description: Vista táctica completa de señales — pendientes, historial reciente, tasa de aprobación y contexto para decisión
user-invocable: true
allowed-tools: Bash, Read
---

Genera una vista táctica completa de las señales de SysMho.

## Señales pendientes ahora

```bash
cd "/home/anderson/Documentos/programas personales/SysMho"
source venv/bin/activate && PYTHONPATH=$(pwd) python3 -c "
import asyncio, asyncpg
from datetime import datetime, timezone
async def main():
    conn = await asyncpg.connect(host='localhost', port=5432, user='postgres', password='ander123', database='sysmho')
    rows = await conn.fetch('''
        SELECT id, symbol, side, win_probability, alert_category, score,
               stop_loss, take_profit, quantity, created_at
        FROM pending_approvals
        WHERE status='PENDING'
        ORDER BY alert_category DESC, score DESC
    ''')
    if not rows:
        print('Sin señales pendientes en este momento.')
    else:
        print(f'{len(rows)} señal(es) esperando decisión:\n')
        now = datetime.now(timezone.utc)
        for r in rows:
            age = int((now - r['created_at'].replace(tzinfo=timezone.utc)).total_seconds())
            remaining = max(0, 300 - age)
            rr = 0
            if r['stop_loss'] and r['take_profit']:
                pass  # calcular R/R si hay datos
            print(f'[{r[\"alert_category\"]}] {r[\"symbol\"]} {r[\"side\"]}')
            print(f'  Confianza: {r[\"win_probability\"]:.0%} | Score: {r[\"score\"]:.2f}')
            print(f'  SL: {r[\"stop_loss\"]} | TP: {r[\"take_profit\"]} | Qty: {r[\"quantity\"]}')
            print(f'  Tiempo restante: {remaining}s | ID: {r[\"id\"]}')
            print()
    await conn.close()
asyncio.run(main())
" 2>&1
```

## Historial reciente (últimas 24h)

```bash
cd "/home/anderson/Documentos/programas personales/SysMho"
source venv/bin/activate && PYTHONPATH=$(pwd) python3 -c "
import asyncio, asyncpg
async def main():
    conn = await asyncpg.connect(host='localhost', port=5432, user='postgres', password='ander123', database='sysmho')
    rows = await conn.fetch('''
        SELECT symbol, side, status, win_probability, alert_category, score, created_at
        FROM pending_approvals
        WHERE created_at >= NOW() - INTERVAL '24 hours'
        ORDER BY created_at DESC
        LIMIT 20
    ''')
    status_icon = {'APPROVED': '✅', 'REJECTED': '❌', 'DISMISSED': '⏱️', 'PENDING': '⏳'}
    print('Últimas 24h:')
    for r in rows:
        icon = status_icon.get(r['status'], '?')
        print(f'{icon} {r[\"symbol\"]} {r[\"side\"]} | {r[\"alert_category\"]} | conf={r[\"win_probability\"]:.0%} | {r[\"created_at\"].strftime(\"%H:%M\")}')

    # Tasas de aprobación
    stats = await conn.fetchrow('''
        SELECT
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE status='APPROVED') as aprobadas,
            COUNT(*) FILTER (WHERE status='REJECTED') as rechazadas,
            COUNT(*) FILTER (WHERE status='DISMISSED') as expiradas
        FROM pending_approvals
        WHERE created_at >= NOW() - INTERVAL '24 hours'
    ''')
    print(f'\nTasa de aprobación: {stats[\"aprobadas\"]}/{stats[\"total\"]} ({stats[\"aprobadas\"]/max(stats[\"total\"],1)*100:.0f}%)')
    print(f'Rechazadas: {stats[\"rechazadas\"]} | Expiradas: {stats[\"expiradas\"]}')
    await conn.close()
asyncio.run(main())
" 2>&1
```

## Contexto de modo actual

Lee `src/runtime_state.json` y muestra si el sistema está en modo MANUAL o AUTÓNOMO, ya que cambia cómo interpretar las señales pendientes.
