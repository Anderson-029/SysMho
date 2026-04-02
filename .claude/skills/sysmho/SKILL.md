---
name: sysmho
description: Panel maestro de SysMho — ejecuta diagnóstico completo del sistema en un solo comando
user-invocable: true
allowed-tools: Bash, Read
---

Eres el panel de control maestro de SysMho v15.2.0. Ejecuta este diagnóstico completo en orden y presenta todo en un reporte estructurado y visual.

---

## BLOQUE 1 — PROCESOS Y SISTEMA

```bash
ps aux | grep -E "uvicorn|src\.main" | grep -v grep
pg_isready -h localhost -p 5432 -U postgres 2>&1
```

Muestra:
- Dashboard (FastAPI): ✅ corriendo / ❌ detenido
- Motor (main.py): ✅ corriendo / ❌ detenido
- PostgreSQL: ✅ disponible / ❌ caído

---

## BLOQUE 2 — ESTADO RUNTIME

Lee `src/runtime_state.json` y muestra:
- Modo: **AUTÓNOMO** o **MANUAL**
- Circuit Breaker: activo o OK
- PnL reset: cuándo fue el último
- Sync status: idle o sincronizando

---

## BLOQUE 3 — TELEMETRÍA RECIENTE

```bash
tail -30 "/home/anderson/Documentos/programas personales/SysMho/src/sysmho_brain.log" 2>/dev/null
```

Agrupa y muestra solo lo relevante:
- ❌ Errores de las últimas horas
- 🛑 Circuit Breaker: si se activó
- 🤖 Últimas decisiones autónomas (APPROVED/REJECTED)
- ✅ Últimas ejecuciones de órdenes

---

## BLOQUE 4 — MÉTRICAS DEL DÍA (desde la BD)

Usa el MCP de PostgreSQL o Bash con psql para consultar:

```sql
-- Trades del día
SELECT COUNT(*) as trades_hoy,
       COUNT(*) FILTER (WHERE pnl > 0) as ganadores,
       ROUND(SUM(pnl)::numeric, 2) as pnl_realizado
FROM trades
WHERE status = 'CLOSED'
  AND executed_at >= CURRENT_DATE;

-- Posiciones abiertas
SELECT COUNT(*) as abiertas,
       ROUND(COALESCE(SUM(pnl_unrealized),0)::numeric, 2) as pnl_flotante
FROM positions;

-- Últimas 3 decisiones autónomas
SELECT symbol, decision, meta_score, created_at
FROM autonomous_decisions
ORDER BY created_at DESC LIMIT 3;
```

Si psql no está disponible usa:
```bash
cd "/home/anderson/Documentos/programas personales/SysMho"
source venv/bin/activate && PYTHONPATH=$(pwd) python3 -c "
import asyncio, asyncpg, os
from dotenv import load_dotenv
load_dotenv()
async def main():
    conn = await asyncpg.connect(host='localhost', port=5432, user='postgres', password='ander123', database='sysmho')
    trades = await conn.fetchrow(\"SELECT COUNT(*) as t, COUNT(*) FILTER (WHERE pnl>0) as w, COALESCE(SUM(pnl),0) as pnl FROM trades WHERE status='CLOSED' AND executed_at>=CURRENT_DATE\")
    pos = await conn.fetchrow(\"SELECT COUNT(*) as c, COALESCE(SUM(pnl_unrealized),0) as fp FROM positions\")
    print(f'Trades hoy: {trades[\"t\"]} | Ganadores: {trades[\"w\"]} | PnL: {trades[\"pnl\"]:.2f}')
    print(f'Posiciones abiertas: {pos[\"c\"]} | PnL flotante: {pos[\"fp\"]:.2f}')
    await conn.close()
asyncio.run(main())
" 2>&1
```

---

## BLOQUE 5 — SEÑALES PENDIENTES

```bash
cd "/home/anderson/Documentos/programas personales/SysMho"
source venv/bin/activate && PYTHONPATH=$(pwd) python3 -c "
import asyncio, asyncpg
async def main():
    conn = await asyncpg.connect(host='localhost', port=5432, user='postgres', password='ander123', database='sysmho')
    rows = await conn.fetch(\"SELECT symbol, side, win_probability, alert_category, score, created_at FROM pending_approvals WHERE status='PENDING' ORDER BY score DESC\")
    if rows:
        for r in rows:
            mins = (asyncio.get_event_loop().time())
            print(f'{r[\"alert_category\"]} | {r[\"symbol\"]} | {r[\"side\"]} | conf={r[\"win_probability\"]:.0%} | score={r[\"score\"]:.2f}')
    else:
        print('Sin señales pendientes')
    await conn.close()
asyncio.run(main())
" 2>&1
```

---

## FORMATO FINAL DEL REPORTE

Presenta todo como un panel de comando limpio:

```
╔══════════════════════════════════════════════════╗
║         SYSMHO v15.2.0 — Panel Maestro           ║
╠══════════════════════════════════════════════════╣
║ Dashboard: ✅  Motor: ✅  BD: ✅                  ║
║ Modo: AUTÓNOMO  CB: OK  Sync: idle               ║
╠══════════════════════════════════════════════════╣
║ HOY: X trades | X ganadores | PnL: $X.XX         ║
║ Abiertos: X posiciones | Flotante: $X.XX         ║
╠══════════════════════════════════════════════════╣
║ SEÑALES PENDIENTES: X                            ║
║  ...                                             ║
╠══════════════════════════════════════════════════╣
║ ÚLTIMOS EVENTOS RELEVANTES                       ║
║  ...                                             ║
╚══════════════════════════════════════════════════╝
```

Si algún bloque falla (proceso caído, BD no responde), márcalo claramente con ❌ y continúa con los demás bloques.
