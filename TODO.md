# TODO — SysMho v15.2.0

## 🎯 Contexto

**Estado actual:** Win rate real 42.4% en 92 trades cerrados, -$114.57 PnL total (vs 87.5% backtest CV).  
**Análisis (2026-04-09):** 2 activos destructivos (POL + BNB) + ventana horaria 14-17 UTC causan ~75% del drawdown.  
**Modelo actual:** XGBoost con 28 features (symbol_encoded incluido), entrenado con Optuna 50 trials, hold-out 86-92%.

---

## ✅ Completado (2026-04-09)

### Arquitectura cerebro consciente del activo
- ✅ `symbol_encoded` feature (#28) — modelo aprende dinámicas específicas por símbolo
- ✅ `SYMBOL_ENCODING` en `constants.py` — encoding estable BTC=0...POL=9
- ✅ `src/analysis/features.py` — inyecta `symbol_encoded` en PASO 4
- ✅ Reentrenado XGBoost con 28 features, Optuna 50 trials, hold-out 86-92%

### MetaEvaluador dinámico por activo
- ✅ Umbral dinámico = 0.52 + max(0, (0.50 - WR_activo) × 0.40), cap 0.75
- ✅ BNB (20% WR) → umbral 0.638 | POL (25% WR) → 0.617 | BTC (79% WR) → 0.520

### Ventana horaria destructiva
- ✅ Filtro 14-17 UTC en `_autonomous_decide()` — WR histórico 33% (vs 42% global)
- ✅ Configurable via `.env` (DESTRUCTIVE_HOUR_START / DESTRUCTIVE_HOUR_END)
- ✅ Penalización +0.08 al MetaEvaluador en esa ventana

### Sliding Window en retrain
- ✅ `TRAINING_WINDOW_MONTHS = 3` en `constants.py`
- ✅ `src/ai/trainer.py` — argumento `--window-months` (default: 3)
- ✅ `src/ai/trainers/sequential.py` — pasa `limit` a `get_master_dataframe()`
- ✅ `src/ai/trainers/tuner.py` — pasa `limit` a `get_master_dataframe()`
- ✅ Próximo retrain: `uv run python -m src.ai.trainer --symbol ALL --timeframe 5m --tune --trials 50`

---

## ✅ Completado (2026-04-06)

- ✅ `CLAUDE.md` compacto + `AGENTS.md` índice optimizado
- ✅ XGBoost compatible con v3.2.0 (load_dotenv + params fix)
- ✅ Engine operacional: 10 WebSockets, SelfLearner activo, Dashboard puerto 8000

---

## 🚀 Pendiente (PRIORIDAD)

### FASE 1 — Fixes de Rendimiento (Alta prioridad)

#### 1. Guardar `signal_source` en trades
- `src/main.py:dispatch_signal()` → pasar `signal_source="BOUNTY"` o `"REGULAR"`
- `src/executor/trader.py:execute_trade()` → guardar en BD
- Tabla `trades` → agregar columna `signal_source VARCHAR(20)` si no existe
- **Por qué:** No se puede auditar qué estrategia funciona mejor (BOUNTY vs REGULAR)
- **Impacto futuro:** Base para Phase 2 meta-modelo

#### 2. Analizar BOUNTY vs REGULAR (después de signal_source)
- ¿BOUNTY WR > REGULAR WR por activo?
- Base para Phase 2: entrenar meta-modelo que prefiera BOUNTY automáticamente

#### 3. Aumentar NORMAL_MIN_CONFIDENCE 0.38 → 0.45
- Solo si WR sigue < 50% después de acumular 100+ trades con fixes actuales
- `.env` → `NORMAL_MIN_CONFIDENCE=0.45`

---

### FASE 2 — Escalabilidad

#### 4. Recolectar 200+ trades en testnet
- Medir nuevo win rate con todos los fixes aplicados
- Umbral para Phase 2: WR consistente > 55% durante 2 semanas

#### 5. Retrain mensual automático con sliding window
- Programar retrain cada 30 días via cron o scheduler
- Usar: `uv run python -m src.ai.trainer --symbol ALL --timeframe 5m --window-months 3`

---

### FASE 3 — Autonomía Plena

#### 6. Mainnet
- Cuando WR > 55% consistente en testnet (2 semanas mínimo)
- Verificar Binance mainnet KYC/verification

---

## 📊 Estimación de mejora post-fixes

| Métrica | Actual | Esperado post-fixes |
|---------|--------|---------------------|
| Win rate | 42.4% | 55-60% |
| PnL (closed) | -$114.57 | ~-$28.65 |
| Drawdown | -$114.57 | -75% (elimina 14-17 UTC + POL/BNB) |
| signal_source | NULL | Auditable (BOUNTY vs REGULAR) |

---

## 🔗 Referencias

- `src/constants.py` — SYMBOLS, MODEL_FEATURES, TRAINING_WINDOW_MONTHS
- `src/ai/trainer.py` — orquestador de entrenamiento
- `src/ai/trainers/sequential.py` — sliding window implementado
- `src/ai/meta_evaluator.py` — umbrales dinámicos por activo
- `src/main.py` — dispatch_signal, _autonomous_decide
- `.env` — DESTRUCTIVE_HOUR_START/END, CB_* thresholds
