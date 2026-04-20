# ADR-001: XGBoost como Motor de Predicción

**Date:** 2026-04-20
**Status:** Accepted
**Deciders:** Anderson

## Context

SysMho necesita clasificar señales de trading en tiempo real, evaluando 10 activos cada 5 minutos. Los requisitos eran estrictos:
- Latencia de inferencia <10ms (no puede bloquear el event loop de asyncio)
- Accuracy >85% con datos de series temporales financieras
- Probabilidades calibradas (no solo la clase predicha — se necesita `confidence`)
- Interpretabilidad: saber qué features impulsan cada predicción

Alternativas evaluadas:
- **LSTM/Transformer**: Captura secuencias temporales largas pero latencia 100-500ms. Overfitting severo con <100k samples por símbolo. Requiere GPU para entrenamiento razonable.
- **Random Forest**: Más rápido que gradient boosting pero sin calibración de probabilidades nativa. Accuracy inferior en datos financieros tabulares.
- **Reglas estáticas (RSI, MACD thresholds)**: Sin adaptación al régimen de mercado. Alto ruido en mercados ranging.
- **Regresión logística**: Demasiado simple para capturar interacciones no-lineales entre 28 features.

## Decision

XGBoost (gradient boosted trees) con clasificación multiclase:
- **Clases:** SELL=0, WAIT=1, BUY=2
- **Features:** 28 features normalizadas (ver `src/constants.py` MODEL_FEATURES)
- **Hiperparámetros** (tuned con Optuna Bayesian search): n_estimators=235, learning_rate=0.1259, max_depth=5, subsample=0.8, colsample_bytree=0.9
- **Entrenamiento:** TimeSeriesSplit (5 folds, sin shuffle — preserva orden temporal)
- **Label threshold:** 0.7% movimiento de precio en la siguiente vela
- **Implementación:** `src/ai/predictor.py` (inferencia), `src/ai/trainer.py` (entrenamiento)

## Consequences

### Positivas
- Inferencia <1ms (XGBoost en CPU es extremadamente rápido para tabular data)
- `predict_proba()` devuelve probabilidades calibradas por clase
- Feature importance nativa — interpretable sin tools adicionales
- Entrenamiento en 5-10 minutos (Fast mode) o 30-60 min (con Optuna)
- Funciona bien con class imbalance mitigado por `sample_weight`

### Negativas / Trade-offs
- No adapta pesos online — requiere retraining periódico (cada 1-2 semanas)
- No captura dependencias temporales largas (>3 meses de historia)
- Sensible al cambio de distribución (market regime shift post-evento macro)

### Deuda Técnica
- Si el mercado cambia drásticamente (e.g., regulación cripto global, flash crash), el modelo puede degradarse silenciosamente antes del próximo retraining
- Se recomienda monitorear accuracy en producción vía `model_performance` tabla
