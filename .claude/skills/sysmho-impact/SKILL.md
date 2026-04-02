---
name: sysmho-impact
description: Análisis de impacto profundo antes de modificar un archivo — dependencias transitivas, tablas BD, env vars y riesgo de regresión
user-invocable: true
allowed-tools: Read, Grep, Glob, Bash
---

El usuario indica un archivo específico a analizar.
Si no lo indica, pregunta cuál quiere revisar antes de modificar.

## Paso 1 — Leer el archivo completo

Lee el archivo indicado completamente. Identifica:
- Propósito principal
- Clases y funciones públicas
- Estado mutable que mantiene

## Paso 2 — Árbol de dependencias (2 niveles)

**Nivel 1 — Quién importa este archivo:**
```bash
MODULO=$(basename ARCHIVO .py)
grep -rn "from.*$MODULO import\|import.*$MODULO" \
  "/home/anderson/Documentos/programas personales/SysMho/src" \
  --include="*.py"
```

**Nivel 2 — Quién importa a los que importan este archivo:**
Repite el grep para cada archivo encontrado en nivel 1.

## Paso 3 — Tablas BD y queries

```bash
grep -n "SELECT\|INSERT\|UPDATE\|DELETE\|FROM\|JOIN" ARCHIVO -i
```

Para cada tabla encontrada, verifica en los otros módulos si hay escritura concurrente posible.

## Paso 4 — Variables de entorno

```bash
grep -n "os\.getenv\|os\.environ" ARCHIVO
```

Verifica que estén en `.env`:
```bash
grep -E "VARIABLE" "/home/anderson/Documentos/programas personales/SysMho/.env"
```

## Paso 5 — Side effects

Identifica:
- ¿Escribe al sistema de archivos? (`open`, `write`, `os.replace`, `json.dump`)
- ¿Escribe a BD? (INSERT, UPDATE, DELETE)
- ¿Hace llamadas a Binance? (`exchange`, `ccxt`, `fetch_`)
- ¿Modifica `runtime_state.json`? (`_save`, `set_autonomous`, `set_sync_status`)
- ¿Está en un loop crítico de `main.py`? (task de asyncio)

## Paso 6 — Tests actuales

```bash
grep -rn "$(basename ARCHIVO .py)" \
  "/home/anderson/Documentos/programas personales/SysMho/tests" \
  --include="*.py"
```

Señala qué funciones tienen test y cuáles no.

## Paso 7 — Reporte de impacto

```
ARCHIVO: src/executor/circuit_breaker.py
Propósito: Evaluador de condiciones sistémicas de bloqueo
─────────────────────────────────────────────────────────
DEPENDIENTES DIRECTOS (nivel 1):
  src/main.py          — _autonomous_decide() llama check()
  src/dashboard/routes/autonomous.py — describe() para API

DEPENDIENTES INDIRECTOS (nivel 2):
  ninguno adicional

TABLAS BD:      ninguna (solo recibe datos, no accede a BD)
ENV VARS:       CB_MAX_POSITIONS, CB_MAX_DAILY_TRADES,
                CB_MAX_CONSEC_LOSSES, CB_DAILY_LOSS_PCT,
                CB_WEEKLY_DRAWDOWN_PCT  → todas en .env ✅
SIDE EFFECTS:   ninguno — función pura
LOOP CRÍTICO:   sí — llamado en cada señal autónoma

TESTS:          tests/test_phase5.py — cobertura básica
                ⚠️ Sin test para valores límite exactos

RIESGO DE CAMBIO: MEDIO
ARCHIVOS QUE DEBES ACTUALIZAR SI CAMBIAS LA INTERFAZ:
  src/main.py:437 — check() con 5 parámetros
  src/dashboard/routes/autonomous.py:61 — check() idem
```
