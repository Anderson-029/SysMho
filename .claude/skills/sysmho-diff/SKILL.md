---
name: sysmho-diff
description: Mapea el impacto cruzado entre archivos antes de tocar un área — qué archivos se relacionan, qué SQL hacen y qué tests los cubren
user-invocable: true
allowed-tools: Read, Grep, Glob, Bash
---

El usuario indica un área o feature (ej. "circuit breaker", "posiciones", "portfolio", "MetaEvaluador").
Si no indica nada, pregunta qué área quiere analizar.

## Paso 1 — Identificar archivos del área

Busca todos los archivos Python que mencionan el término indicado:

```bash
grep -rn "TÉRMINO" \
  "/home/anderson/Documentos/programas personales/SysMho/src" \
  --include="*.py" -l
```

Lee cada archivo encontrado para entender su rol en el área.

## Paso 2 — Mapa de dependencias cruzadas

Para cada archivo del área, encuentra:
- **Quién lo importa** (quién depende de él):
```bash
grep -rn "from src.MODULO import\|import src.MODULO" \
  "/home/anderson/Documentos/programas personales/SysMho/src" \
  --include="*.py" -l
```
- **Qué importa él** (de qué depende):
```bash
grep -E "^from|^import" ARCHIVO
```

## Paso 3 — Queries SQL involucradas

Para cada archivo del área:
```bash
grep -n "SELECT\|INSERT\|UPDATE\|DELETE" ARCHIVO --include="*.py" -i
```

Lista las tablas que toca y si hay riesgo de conflicto de escritura concurrente.

## Paso 4 — Cobertura de tests

```bash
grep -rn "TÉRMINO" \
  "/home/anderson/Documentos/programas personales/SysMho/tests" \
  --include="*.py" -l
```

Para cada test encontrado, lee las primeras 30 líneas para entender qué cubre exactamente.

## Paso 5 — Reporte de impacto

Presenta:
```
ÁREA ANALIZADA: [nombre]
─────────────────────────────────────────────────────
ARCHIVOS DEL ÁREA:
  src/executor/circuit_breaker.py — CircuitBreaker
  src/main.py — usa CircuitBreaker en _autonomous_decide()
  src/dashboard/routes/autonomous.py — expone estado CB vía API

DEPENDENCIAS:
  circuit_breaker.py → importado por: main.py, autonomous.py
  autonomous.py → importa: runtime_config, circuit_breaker

TABLAS BD AFECTADAS:
  trades (READ)
  autonomous_decisions (WRITE)

TESTS QUE CUBREN ESTA ÁREA:
  tests/test_phase5.py — CircuitBreaker básico
  ⚠️ Sin test para: reset_circuit_breaker() + interacción con MetaEvaluador

RIESGO DE CAMBIO: ALTO / MEDIO / BAJO
RECOMENDACIÓN: ...
```
