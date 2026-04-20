# ADR-003: Circuit Breaker para Protección de Capital

**Date:** 2026-04-20
**Status:** Accepted
**Deciders:** Anderson

## Context

En modo autónomo, SysMho ejecuta trades sin intervención humana. Sin límites duros, una racha de pérdidas o período de alta volatilidad podría liquidar la cuenta antes de que Anderson intervenga. El MetaEvaluador filtra señales estadísticamente malas, pero no protege contra escenarios sistémicos (flash crash, error de datos, bug en el predictor).

Se necesitaba una capa de protección de capital que:
- Fuera independiente de la lógica de predicción (no bypaseable por el modelo)
- Tuviera parámetros ajustables sin reiniciar el sistema
- Bloqueara completamente (no parcialmente) cuando se activara

## Decision

5 hard stops implementados en `src/executor/circuit_breaker.py`:

| Stop | Parámetro .env | Default | Condición de disparo |
|------|----------------|---------|----------------------|
| Drawdown diario | `CB_DAILY_LOSS_PCT` | 4% | PnL diario ≤ -4% del capital |
| Drawdown semanal | `CB_WEEKLY_DRAWDOWN_PCT` | 8% | PnL semanal ≤ -8% del capital |
| Pérdidas consecutivas | `CB_MAX_CONSEC_LOSSES` | 3 | 3 pérdidas seguidas sin ganancia |
| Posiciones abiertas | `CB_MAX_OPEN_POSITIONS` | 3 | ≥3 posiciones simultáneas |
| Trades diarios | `CB_MAX_DAILY_TRADES` | 8 | ≥8 trades en el día |

Evaluación: `CircuitBreaker.check()` se llama en cada intento de aprobación autónoma, **antes** de `TradeExecutor.execute_trade()`.

Reset: Manual desde dashboard (`POST /api/autonomous/reset_cb`) o automático al día siguiente.

## Consequences

### Positivas
- Capital protegido en escenarios adversos (racha de pérdidas, alta volatilidad)
- Todos los parámetros configurables en `.env` sin reiniciar el engine
- Independiente del modelo ML — no puede ser "engañado" por el predictor
- Reset manual disponible desde dashboard en tiempo real

### Negativas / Trade-offs
- Puede frenar el sistema en mercados volátiles que generen oportunidades reales
- Los defaults (4% diario, 8% semanal) son conservadores — puede ser muy restrictivo para estrategias agresivas
- El stop de posiciones (3 simultáneas) limita la diversificación

### Deuda Técnica
- No hay notificación cuando el CB se dispara (solo logs en `sysmho_brain.log`)
- El reset automático diario requiere que el engine esté corriendo para triggerarse
- No hay CB por activo individual (es global) — un activo muy volátil puede bloquear los otros 9
