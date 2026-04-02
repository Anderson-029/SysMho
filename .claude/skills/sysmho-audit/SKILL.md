---
name: sysmho-audit
description: Auditoría de integridad completa — verifica coherencia entre BD local, Binance y estado del sistema
user-invocable: true
allowed-tools: Bash, Read
---

Ejecuta una auditoría de integridad completa de SysMho. Detecta inconsistencias entre la BD local y el estado real del sistema.

## CHECK 1 — Consistencia de posiciones

```bash
cd "/home/anderson/Documentos/programas personales/SysMho"
source venv/bin/activate && PYTHONPATH=$(pwd) python3 -c "
import asyncio, asyncpg
async def main():
    conn = await asyncpg.connect(host='localhost', port=5432, user='postgres', password='ander123', database='sysmho')
    pos = await conn.fetch('SELECT symbol, side, quantity, entry_price, invested_usdt, pnl_unrealized FROM positions ORDER BY symbol')
    print(f'Posiciones en BD: {len(pos)}')
    for p in pos:
        print(f'  {p[\"symbol\"]} {p[\"side\"]} qty={p[\"quantity\"]} entry={p[\"entry_price\"]} invested={p[\"invested_usdt\"]:.2f}')
    await conn.close()
asyncio.run(main())
" 2>&1
```

## CHECK 2 — Consistencia del portafolio

```bash
cd "/home/anderson/Documentos/programas personales/SysMho"
source venv/bin/activate && PYTHONPATH=$(pwd) python3 -c "
import asyncio, asyncpg
async def main():
    conn = await asyncpg.connect(host='localhost', port=5432, user='postgres', password='ander123', database='sysmho')
    port = await conn.fetchrow('SELECT total_balance, available_balance, in_positions, recorded_at FROM portfolio ORDER BY recorded_at DESC LIMIT 1')
    in_pos_real = await conn.fetchval('SELECT COALESCE(SUM(invested_usdt), 0) FROM positions')
    print(f'Portfolio snapshot: total={port[\"total_balance\"]:.2f} available={port[\"available_balance\"]:.2f} in_positions={port[\"in_positions\"]:.2f}')
    print(f'Sum real de positions.invested_usdt: {in_pos_real:.2f}')
    diff = abs(float(port[\"in_positions\"]) - float(in_pos_real))
    print(f'Diferencia: {diff:.2f} — {\"✅ OK\" if diff < 0.1 else \"❌ INCONSISTENTE\"}')
    await conn.close()
asyncio.run(main())
" 2>&1
```

## CHECK 3 — Trades en estado inválido

```bash
cd "/home/anderson/Documentos/programas personales/SysMho"
source venv/bin/activate && PYTHONPATH=$(pwd) python3 -c "
import asyncio, asyncpg
async def main():
    conn = await asyncpg.connect(host='localhost', port=5432, user='postgres', password='ander123', database='sysmho')
    # Trades OPEN sin posición correspondiente
    orphan = await conn.fetch(\"SELECT t.id, t.symbol, t.side FROM trades t LEFT JOIN positions p ON t.symbol=p.symbol WHERE t.status='OPEN' AND p.symbol IS NULL\")
    # Señales pendientes viejas (más de 10 min)
    stale = await conn.fetch(\"SELECT id, symbol, created_at FROM pending_approvals WHERE status='PENDING' AND created_at < NOW() - INTERVAL '10 minutes'\")
    print(f'Trades OPEN sin posición: {len(orphan)} {\"❌\" if orphan else \"✅\"}')
    for o in orphan:
        print(f'  id={o[\"id\"]} {o[\"symbol\"]} {o[\"side\"]}')
    print(f'Señales PENDING viejas (+10min): {len(stale)} {\"⚠️\" if stale else \"✅\"}')
    await conn.close()
asyncio.run(main())
" 2>&1
```

## CHECK 4 — Salud del runtime

Lee `src/runtime_state.json` y verifica:
- El archivo existe y es JSON válido
- Los timestamps de reset son coherentes (no en el futuro)
- El sync_status no está atascado en 'syncing'

## CHECK 5 — Log de errores recientes

```bash
grep -E "ERROR|Exception|Traceback|❌" \
  "/home/anderson/Documentos/programas personales/SysMho/src/sysmho_brain.log" \
  2>/dev/null | tail -20
```

## Reporte Final

```
AUDITORÍA SYSMHO — [FECHA]
─────────────────────────────────────
Posiciones BD:        ✅/❌ N encontradas
Consistencia port:    ✅/❌ diferencia $X
Trades huérfanos:     ✅/❌
Señales obsoletas:    ✅/⚠️
Runtime state:        ✅/❌
Errores recientes:    ✅/❌ N errores

VEREDICTO: SISTEMA ÍNTEGRO / REVISAR ITEMS ❌
```
