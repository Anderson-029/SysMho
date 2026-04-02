---
name: sysmho-test-coverage
description: Mapea qué módulos tienen tests, qué funciones críticas NO están cubiertas y sugiere qué tests escribir primero
user-invocable: true
allowed-tools: Read, Grep, Glob, Bash
---

## Paso 1 — Inventario de módulos

Lista todos los módulos fuente:
```bash
find "/home/anderson/Documentos/programas personales/SysMho/src" \
  -name "*.py" | sort
```

## Paso 2 — Inventario de tests existentes

```bash
find "/home/anderson/Documentos/programas personales/SysMho/tests" \
  -name "*.py" | sort
```

Lee el inicio de cada test file para entender qué cubre.

## Paso 3 — Ejecutar tests y ver estado actual

```bash
cd "/home/anderson/Documentos/programas personales/SysMho"
source venv/bin/activate && PYTHONPATH=$(pwd) pytest tests/ -v --tb=no -q 2>&1
```

## Paso 4 — Cruzar módulos vs tests

Para cada módulo crítico, busca si hay test:
```bash
grep -rn "circuit_breaker\|meta_evaluator\|predictor\|risk\|trader\|monitor\|repository\|features\|gap_filler" \
  "/home/anderson/Documentos/programas personales/SysMho/tests" \
  --include="*.py" -l
```

Lee los tests encontrados para entender profundidad de cobertura.

## Paso 5 — Identificar funciones críticas sin test

Son críticas si:
- Hacen llamadas a Binance (dinero real)
- Escriben a la BD (trades, posiciones, portfolio)
- Toman decisiones autónomas (MetaEvaluador, CircuitBreaker)
- Calculan PnL o position sizing

## Paso 6 — Reporte de cobertura

```
COBERTURA DE TESTS — SYSMHO
─────────────────────────────────────────────────────
MÓDULOS CON COBERTURA:
  ✅ circuit_breaker.py  → test_phase5.py (básico)
  ✅ predictor.py        → test_phase3.py
  ✅ features.py         → test_phase2.py
  ...

MÓDULOS SIN COBERTURA:
  ❌ meta_evaluator.py   — CRÍTICO: toma decisiones autónomas
  ❌ self_learner.py     — IMPORTANTE: escribe meta_stats.json
  ❌ gap_filler.py       — MODERADO: lógica de detección de gaps
  ❌ runtime_config.py   — BAJO: funciones simples de archivo

FUNCIONES CRÍTICAS SIN TEST:
  ❌ MetaEvaluador.evaluate() — aprueba/rechaza trades reales
  ❌ RiskManager.evaluate_signal() — calcula position sizing
  ❌ PositionMonitor._close_position() — cierra con dinero real
  ❌ TradeExecutor.execute_trade() — envia órdenes a Binance

TESTS A ESCRIBIR (por prioridad):
  1. test_meta_evaluator.py — mockear stats y verificar score
  2. test_risk_manager.py — verificar position sizing y límites
  3. test_self_learner.py — verificar actualización de win_rate
  4. test_gap_filler.py — verificar detección de gaps

¿Quieres que genere los tests faltantes?
```
