# ADR-002: Sliding Window de 3 Meses para Entrenamiento

**Date:** 2026-04-20
**Status:** Accepted
**Deciders:** Anderson

## Context

El mercado cripto cambia de régimen (bull/bear/sideways) cada 2-3 meses. Los patrones que predijeron bien en un mercado alcista de 2024 pueden ser engañosos en un mercado bajista de 2025. El sistema necesita una estrategia de retraining que balance:
- **Adaptabilidad:** Aprender del régimen actual
- **Estabilidad:** No olvidar patrones importantes por falta de datos

Opciones evaluadas:
- **Histórico completo (2020-presente):** El modelo aprende todos los regímenes pero puede confundir patrones de mercados muy diferentes. Dataset enorme → entrenamiento lento.
- **Ventana fija 1 mes:** Muy adaptable pero insuficientes datos para TimeSeriesSplit robusto.
- **Ventana fija 6 meses:** Más estable pero demasiado lento en adaptarse.
- **Ventana deslizante 3 meses:** Balance entre adaptabilidad y estabilidad.

## Decision

`TRAINING_WINDOW_MONTHS = 3` (configurado en `src/constants.py`)

- **Tamaño:** 25,920 velas 5m (30 días × 24h × 12 × 3 meses)
- **Implementación:** `src/ai/trainers/sequential.py` — cada retraining toma las últimas N velas desde la fecha actual
- **Frecuencia recomendada:** Cada 1-2 semanas vía `uv run python -m src.ai.trainer --symbol ALL --timeframe 5m`
- **Activación automática:** `AUTO_TRAIN_CHECK_SECONDS = 3600` en engine (evalúa si reentrenar cada hora)

## Consequences

### Positivas
- El modelo refleja el régimen de mercado actual (últimos 3 meses)
- Dataset manejable: ~220,000 filas para 10 símbolos (rápido de entrenar)
- TimeSeriesSplit con 5 folds funciona bien con esta cantidad de datos
- Gap Filler (`src/collector/gap_filler.py`) asegura que la ventana siempre esté completa

### Negativas / Trade-offs
- Pierde patrones de >3 meses de antigüedad
- Si el mercado entra en un régimen sin precedente en los últimos 3 meses, el modelo puede fallar
- Requiere retraining frecuente para mantenerse relevante

### Deuda Técnica
- `TRAINING_WINDOW_MONTHS` es configurable pero no está expuesto en `.env` — si se quiere cambiar hay que editar `src/constants.py`
- No hay alertas automáticas cuando el accuracy en producción cae (monitoreo manual)
