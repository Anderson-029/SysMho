# TODO — SysMho v15.2.0

## 🎯 Contexto

**Estado actual:** Win rate real 44% en 75 trades (vs 87.5% backtest).  
**Causa:** Filtros insuficientes permiten trades de baja confianza. 4 cambios van a mejorar a 55%+.

---

## 📋 Tareas Pendientes

### 1️⃣ Excluir POL/USDT del portafolio activo

**Por qué:**  
- 16 trades, 25% WR, -$53.15 PnL (peor activo)
- Destruye el portafolio: sin POL, PnL global mejora -$104.31 → -$51.16 (+49%)
- Varianza CV 17% (vs 3-8% otros activos) → modelo inestable en este par

**Qué cambiar:**  
- `src/collector/market_data.py` → agregar `POL/USDT` a `EXCLUDED_SYMBOLS`
- O remover de `SYMBOLS` en `src/constants.py`

**Impacto:** +50% PnL, elimina el activo más dañino

---

### 2️⃣ Pausar ejecución de trades 9-14 UTC

**Por qué:**  
- 23 trades en esas horas: 17-33% WR (vs 55%+ otras horas)
- 31% del volumen de trades = 116% de las pérdidas acumuladas
- Horas débiles correlacionadas con Londres cierre / Asia apertura

**Qué cambiar:**  
- `src/main.py:dispatch_signal()` → revisar `datetime.utcnow().hour` antes de `execute_trade()`
- Guardar en log: "⏭️ [PAUSA] Hora débil 9-14 UTC, señal rechazada"

**Impacto:** -23 trades malos, mejora win rate a ~52%

---

### 3️⃣ Aumentar NORMAL_MIN_CONFIDENCE de 0.38 → 0.45

**Por qué:**  
- Umbral actual muy permisivo: toma trades con 38% confianza (casi aleatorio)
- Backtest 87.5% significa que model IS correcto, pero filtro inicial es insuficiente
- XGBoost prob_wait > 72% veta la señal, pero prob_dominant >= 38% no es filtro real

**Qué cambiar:**  
- `.env` → `NORMAL_MIN_CONFIDENCE=0.45` (o 0.48 si quieres más conservador)
- O guardar en `src/constants.py` si es constante del proyecto

**Impacto:** -12 trades débiles, gana precisión sin perder señales buenas

---

### 4️⃣ Guardar `signal_source` en trades (BOUNTY vs REGULAR)

**Por qué:**  
- Actualmente `signal_source` siempre NULL en tabla `trades`
- No puedes analizar si BOUNTY signals (alta convicción) cumplen mejor que REGULAR (top 3)
- Necesario para fase 2 meta-modelo (distinguir cuál estrategia funciona)

**Qué cambiar:**  
- `src/main.py:dispatch_signal()` → pasar `signal_source="BOUNTY"` o `"REGULAR"` al crear signal
- `src/executor/trader.py:execute_trade()` → guardar `signal_source` en DB al insertar en `trades`
- Agregar columna en BD si no existe: `ALTER TABLE trades ADD COLUMN signal_source VARCHAR(20);`

**Impacto:** 
- Inmediato: ninguno (sin cambiar lógica)
- Futuro: análisis granular BOUNTY (convicción 55%+) vs REGULAR (top 3)

---

## ✅ Completado (2026-04-06)

### Documentación optimizada
- ✅ Creado `CLAUDE.md` (manifest compacto, 170 líneas)
- ✅ Refactorizado `AGENTS.md` (índice de 17 skills)
- ✅ Guardado en memory: estrategia doc para futuras conversaciones

### Modelo XGBoost compatible
- ✅ Identificado: incompatibilidad XGBoost 3.2.0 vs v1_1 guardado en 3.0.0
- ✅ Arreglado: `load_dotenv()` en trainer.py + XGBClassifier params
- ✅ Reentrenado: xgboost_v1_1.joblib con todos 10 activos (CV: 92.67% BTC, 87.90% ETH, etc)
- ✅ Verificado: ModelPredictor carga sin errores

### Preparación para producción
- ✅ Engine arranca sin crashes
- ✅ Dashboard en puerto 8000 funciona
- ✅ BD conectada (10 tablas, datos frescos)
- ✅ .gitignore actualizado (models, .env, backups ignorados)

---

## 📊 Estimación de mejora

| Métrica | Actual | Post-4-fixes | Mejora |
|---------|--------|-------------|--------|
| Win rate | 44% | 55%+ | +25% |
| PnL | -$104.31 | -$20~30 | +$75 (~70% mejor) |
| Trades rechazados | ~5% | ~30% | Más selectivo |
| Time window | Siempre | 9-14 UTC pausado | -23 trades malos |

---

## 🚀 Próximos pasos (DESPUÉS de los 4 fixes)

1. Acumular 200+ trades autónomos → activar Phase 2 meta-modelo XGBoost
2. Calibrar Circuit Breaker thresholds según resultado real
3. Considerar Optuna tuning (50 trials) si win rate sigue bajo después de fixes
4. Integrar sentimiento (funding rate, OBI) más agresivamente en feature engineering
