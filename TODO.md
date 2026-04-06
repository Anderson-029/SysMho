# TODO — SysMho v15.2.0

## 🎯 Contexto

**Estado actual:** Win rate real 44% en 75 trades (vs 87.5% backtest CV).  
**Análisis:** El modelo XGBoost es correcto (92.67% BTC, 87.90% ETH en CV), pero los **4 filtros downstream** (autonomía, timing, confianza mínima, clasificación) son insuficientes. Estos cambios aplican directamente al motor de decisión autónomo de SysMho para cerrar la brecha backtest ↔ live.

---

## 📋 Tareas Pendientes

### 1️⃣ Excluir POL/USDT del portafolio activo

**Problema en SysMho:**  
- POL/USDT: 16 trades, 25% WR, -$53.15 PnL (contribuye -51% del drawdown total)
- CV accuracy solo 80.55% ± 17.00% (varianza 2.5x mayor que BTC 3.67%)
- MetaEvaluador y CircuitBreaker aprueban trades en POL porque usan stats globales, no por-activo
- Sin POL: PnL global -$104.31 → -$51.16 (+49%), acercándose a backtest positivo

**Por qué es crítico para SysMho:**
- Sistema diseñado para 10 activos seleccionados (SYMBOLS en constants.py)
- POL rompe el supuesto "activos líquidos + predecibles" en el que se basó tuning del modelo
- En testnet no hay fricción (no importan spreads), pero POL volatilidad hace que modelo fracase
- SelfLearner está aprendiendo **patrones destructivos** de POL que reducen confianza global

**Qué cambiar:**  
- `src/constants.py` → remover `POL/USDT` de `SYMBOLS = [...]`
- Alternativa: `src/collector/market_data.py` → agregar a `EXCLUDED_SYMBOLS`
- Verificar que todos los loops (5M_SCANNER, BOUNTY_WATCHER, LEARNING_LOOP) respeten exclusión

**Impacto en SysMho:**
- Elimina el 51% del drawdown
- Meta-Evaluador y SelfLearner aprenden de datos **coherentes**
- CircuitBreaker thresholds se calibran con portafolio real (9 activos, no 10 con ruido)

---

### 2️⃣ Pausar ejecución de trades 9-14 UTC

**Problema en SysMho:**
- En esas horas: 23 trades con 17-33% WR (vs 55%+ otras horas)
- Representan 31% del volumen pero 116% de las pérdidas acumuladas
- Coinciden con: Londres cierre (08:00 UTC) + Asia apertura (12:00+ UTC)
- XGBoost entrenado con datos históricos 2020-2026, pero **período 9-14 UTC tiene dinámica diferente** (menos liquidez, spreads amplios, volatilidad estacional)

**Por qué es crítico para SysMho:**
- Sistema opera en **Binance Futures (perpetuos 24/7)**, pero no todos los timeframes tienen igual volatilidad
- MetaEvaluador NO tiene "componente temporal" → aprueba trades sin considerar hora UTC
- CircuitBreaker tiene máximos diarios pero no máximos por hora
- SelfLearner acumula estadísticas por hora (win_rate_by_hour), pero CONTINÚA ejecutando en horas débiles

**Qué cambiar:**
- `src/main.py:dispatch_signal()` → antes de `executor.execute_trade()`, revisar `datetime.utcnow().hour`
- Lógica: `if hour in range(9, 14): return "PAUSA. Hora débil 9-14 UTC"` (log en `sysmho_brain.log`)
- Aplicar a REGULAR + BOUNTY (ambas estrategias fallan en esas horas)

**Impacto en SysMho:**
- Elimina 23 trades con WR < 35%
- Respeta el "ritmo biológico" del mercado 24/7
- Reduce drawdown sin reducir win rate (filtra ruido, no señales válidas)
- SelfLearner ya reporta stats por hora → usar esa data para mejorar autonomía

---

### 3️⃣ Aumentar NORMAL_MIN_CONFIDENCE de 0.38 → 0.45

**Problema en SysMho:**
- Umbral 0.38 = "levemente más probable BUY que WAIT"
- XGBoost predice [P(SELL), P(WAIT), P(BUY)]; si BUY=0.40, WAIT=0.38, SELL=0.22 → aprueba BUY
- Pero hay **validación cruzada interna**: Inertia filter (WAIT > 72% veta), Strength ratio (dominant/opposite >= 2.0)
- **Estos filtros secundarios NO son suficientes** para el 44% WR real

**Por qué es crítico para SysMho:**
- Modo autónomo (MetaEvaluador + CircuitBreaker) depende de confianza XGBoost como **score base**
- META_SCORE_THRESHOLD = 0.52 ya rechaza ~30% de señales
- Pero los 70% que pasan incluyen muchas con XGBoost confidence 38-45% (borde)
- En backtest CV, ese rango **aún funciona** (87.5% accuracy), pero **en live real market**, esa confianza marginal falla

**Qué cambiar:**
- `.env` → `NORMAL_MIN_CONFIDENCE=0.45` (o 0.48 para más conservador)
- AGGRESSIVE_MIN_CONFIDENCE podría ir 0.35 → 0.40
- Verificar que cambio propague a MetaEvaluator (usa NORMAL_MIN_CONFIDENCE en score_base)

**Impacto en SysMho:**
- Rechaza ~15-20 trades "borderline" que tienden a perder
- Mantiene los ~60 trades de alta confianza (que ganan 50%+ en backtest)
- Reduce volumen pero **mejora precision** (objetivo del sistema: calidad > cantidad)
- Alínea autonomía: MetaEvaluador ya rechaza scores bajos → NORMAL_MIN_CONFIDENCE debe acompañar

---

### 4️⃣ Guardar `signal_source` en tabla `trades`

**Problema en SysMho:**
- Actualmente `signal_source` siempre NULL en tabla trades
- Sistema tiene 2 estrategias: REGULAR (top 3 cada 5m) + BOUNTY (alta convicción, sin horario)
- **No se puede auditar cuál funciona mejor** porque ambas se guardan igual
- SelfLearner aprende de ALL trades, pero no distingue qué estrategia generó cada uno

**Por qué es crítico para SysMho:**
- BOUNTY = indicador de "confianza extrema" (XGBoost >= 55% + 3 tendencias alineadas + R/R >= 3)
- REGULAR = "oportunidad de score alto en ventana de 5m" (puede ser 0.40 XGBoost)
- Backtest 87.5% probablemente dominado por BOUNTY (menos trades, mejor selectividad)
- Live 44% probablemente dominado por REGULAR (más volumen, calidad mixta)
- **Necesitas esta data para Phase 2**: entrenar meta-modelo que sepa "BOUNTY > REGULAR" automáticamente

**Qué cambiar:**
- `src/main.py`: cuando crea signal en `dispatch_signal()`, guardar `signal_source="BOUNTY"` o `"REGULAR"`
- `src/executor/trader.py:execute_trade()`: recibir parámetro `signal_source`, guardar en BD
- `trades` table: agregar columna `signal_source VARCHAR(20)` si no existe
- Asegurar que SelfLearner lee signal_source y lo reporta en meta_stats

**Impacto en SysMho:**
- Cero cambio inmediato en ejecución (sin lógica nueva)
- Futura: análisis granular "BOUNTY win_rate vs REGULAR win_rate por activo"
- Phase 2: entrenar meta-modelo que **automaticamente prefiera BOUNTY** (menos intervención manual)
- Mejor calibración de MetaEvaluador: actualmente usa stats globales, podrá usar stats por signal_source

---

## ✅ Completado (2026-04-06)

### Documentación optimizada
- ✅ Creado `CLAUDE.md` (manifest compacto, 170 líneas)
- ✅ Refactorizado `AGENTS.md` (índice de 17 skills)
- ✅ Guardado en memory: estrategia doc para futuras conversaciones

### Modelo XGBoost compatible
- ✅ Identificado: incompatibilidad XGBoost 3.2.0 vs v1_1 guardado en 3.0.0
- ✅ Arreglado: `load_dotenv()` en trainer.py + XGBClassifier params
- ✅ Reentrenado: xgboost_v1_1.joblib con todos 10 activos (CV: 92.67% BTC, 87.90% ETH, 90.23% BNB, etc)
- ✅ Verificado: ModelPredictor carga sin errores, engine arranca sin crashes

### Sistema operacional
- ✅ Engine en vivo: 10 WebSocket activos, 650 trades acumulados, SelfLearner aprendiendo
- ✅ Dashboard: puerto 8000, interfaz lista para aprobaciones manuales
- ✅ Base de datos: 10 tablas sincronizadas, portfolio $4637.97
- ✅ CircuitBreaker + MetaEvaluador: protección activa, modo MANUAL operacional

---

## 📊 Estimación de mejora (post-4-fixes)

| Métrica | Actual | Post-fixes | Mejora | Justificación |
|---------|--------|-----------|--------|---|
| Win rate | 44% | 55%+ | +25% | Elimina POL (-25% WR), paussa 9-14 UTC (-33% WR), aumenta confianza mín |
| PnL | -$104.31 | -$20~30 | +$75 (~70%) | POL -$53 eliminado; 23 trades malos evitados |
| Trades ejecutados | 75 | 50-60 | -15~25 | Más selectivo (confianza 0.45), menos horas débiles |
| Drawdown | -$104 | -$30 | -71% | Circuito breaker se calibra con 9 activos reales |
| Señales BOUNTY/REGULAR | Desconocido | Auditable | ∞ | Base para Phase 2 meta-modelo |

---

## 🚀 Próximos pasos (DESPUÉS de los 4 fixes)

1. **Implementar 4 fixes** (~30 min total, cuidado con testing en testnet)
2. **Acumular 200+ trades** autónomos en testnet con nuevos filtros
3. **Analizar BOUNTY vs REGULAR**: ¿cuál win rate es más alto?
4. **Phase 2 meta-modelo**: entrenar XGBoost que aprenda "preferir BOUNTY"
5. **Optuna tuning**: si win rate sigue < 50% post-fixes, retuning bayesiano con 100 trials
6. **Mainnet**: cuando win rate consistente > 55% en testnet por 2 semanas

---

## 🔗 Referencias

- `src/main.py`: entry point, loops principales
- `src/constants.py`: SYMBOLS, NORMAL_MIN_CONFIDENCE, MODEL_FEATURES
- `src/ai/meta_evaluator.py`: META_SCORE_THRESHOLD, componentes del score
- `src/executor/circuit_breaker.py`: máximos diarios, límites de posición
- `src/ai/self_learner.py`: actualiza meta_stats con win_rate_by_hour
- `.env`: BINANCE_API_KEY, BINANCE_TESTNET, CB_* thresholds
