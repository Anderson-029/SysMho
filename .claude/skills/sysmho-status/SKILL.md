---
name: sysmho-status
description: Muestra el estado completo del sistema SysMho — procesos, BD, modo autónomo y runtime
user-invocable: true
allowed-tools: Bash, Read
---

Verifica y reporta el estado completo de SysMho en este orden:

1. **Procesos activos**:
```bash
ps aux | grep -E "uvicorn|src.main" | grep -v grep
```
Reporta: ✅ Dashboard corriendo / ❌ Dashboard detenido | ✅ Motor corriendo / ❌ Motor detenido

2. **PostgreSQL**:
```bash
pg_isready -h localhost -p 5432 -U postgres 2>&1
```
Reporta: ✅ BD disponible / ❌ BD no responde

3. **Estado runtime** — lee `src/runtime_state.json`:
   - Modo: AUTÓNOMO o MANUAL
   - cb_reset_at (si existe)
   - pnl_reset_at (si existe)
   - sync_status

4. **Últimas 15 líneas del log neuronal**:
```bash
tail -15 "/home/anderson/Documentos/programas personales/SysMho/src/sysmho_brain.log" 2>/dev/null || echo "Log vacío o no existe"
```

5. **Resumen final** en formato:
```
SYSMHO v15.2.0 — [FECHA Y HORA]
Dashboard: ✅/❌ | Motor: ✅/❌ | BD: ✅/❌
Modo: MANUAL/AUTÓNOMO | CB: activo/OK
```
