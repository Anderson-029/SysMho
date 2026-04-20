# ADR-006: MetaEvaluador como Segunda Capa Estadística

**Date:** 2026-04-20
**Status:** Accepted
**Deciders:** Anderson

## Context

XGBoost alcanza 96-100% accuracy en validación cruzada, pero en trading real la accuracy del modelo no se traduce directamente en win rate de trades. Problemas observados:
- El modelo predecía BUY en BTC durante las horas 14-17 UTC pero estas predicciones tenían win rate real <40% (alta volatilidad, manipulación institucional)
- En activos con historial negativo (e.g., DOT en ciertos regímenes), el modelo seguía generando señales que perdían
- La confianza del modelo (e.g., 45%) no estaba bien calibrada — decir 45% no significaba realmente 45% de probabilidad de ganar

Se necesitaba una segunda capa que filtrara señales usando **estadísticas reales de trades pasados**, no las predicciones del modelo.

Alternativas:
- **Filtros estáticos (ej: no operar 14-17 UTC):** No adaptativos. Lo que es "mala hora" hoy puede no serlo en 3 meses.
- **Ensemble de modelos:** Alta complejidad, difícil de interpretar, retraining más costoso.
- **Umbrales de confianza más altos:** Solo filtra por confianza del modelo, no por contexto histórico real.

## Decision

`MetaEvaluator` en `src/ai/meta_evaluator.py` con 5 componentes estadísticos que calculan un `meta_score` [0,1]:

1. **Win Rate global del símbolo** (peso: 1 componente) — si hay ≥10 trades
2. **Win Rate por hora UTC + dirección** (peso: 1 componente) — si hay ≥5 trades en esa franja
3. **Calibración de confianza** (peso: 1 componente) — ¿el modelo acierta cuando dice X%?
4. **Racha de pérdidas recientes** (penalización: -8% por pérdida extra)
5. **Confianza base del modelo** (peso: 1 componente, siempre incluido)

`meta_score = promedio(componentes activos)`

**Umbral dinámico:** `0.52` base, sube hasta `0.75` si el win rate histórico del activo es bajo.
**Ventana destructiva 14-17 UTC:** +0.08 al umbral (temporal hasta acumular datos by_hour).

`SelfLearner` (`src/ai/self_learner.py`) actualiza `meta_stats.json` tras cada trade cerrado.

## Consequences

### Positivas
- Filtra señales en contextos estadísticamente malos (horas, activos, direcciones)
- Se auto-mejora con cada trade (aprendizaje online via SelfLearner)
- Interpetable: las `reasons` devueltas explican por qué se aprobó/rechazó
- Umbral dinámico por activo — activos con mal historial necesitan más convicción

### Negativas / Trade-offs
- **Cold start:** Los primeros 10 trades por símbolo van sin filtro MetaEvaluador (sin datos históricos)
- Para tener el meta-model completo se necesitan ≥200 trades (`META_MIN_FOR_MODEL`)
- Si SysMho estuvo inactivo, las estadísticas de `meta_stats.json` pueden estar desactualizadas

### Deuda Técnica
- `meta_stats.json` se guarda en disco (`src/ai/models/meta_stats.json`) — no está en BD. Si se pierde el archivo, se pierden las estadísticas acumuladas
- No hay versionado de `meta_stats.json` — un bug en SelfLearner podría corromper el historial silenciosamente
