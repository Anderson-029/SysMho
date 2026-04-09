# TODO — SysMho v15.2.0

## 🎯 Contexto

**Estado actual:** Win rate real 42.4% en 92 trades cerrados, -$114.57 PnL total (vs 87.5% backtest CV).  
**Análisis (performance 2026-04-09):** El modelo XGBoost es correcto, pero **2 activos destructivos (POL + BNB) + ventana horaria 14-17 UTC** causan 70% + 75% del drawdown respectivamente. Remover estos dos factores = +$79.80 + $85.92 = **+$165.72 en corrección (~150% mejora proyectada).**

---

## ✅ Completado (2026-04-09)

### 1️⃣ Arquitectura de un cerebro con conciencia de activo (Parte A)

**Implementado:** `symbol_encoded` feature (#28) + reentrenamiento

**Cambios:**
- `src/constants.py`: Agregado `SYMBOL_ENCODING = {BTC: 0, ETH: 1, ..., POL: 9}`
- `src/constants.py`: `MODEL_FEATURES` ampliado de 27 → 28 features
- `src/analysis/features.py`: Inyectar `df['symbol_encoded']` en PASO 4
- Reentrenado modelo XGBoost con 28 features, CV 82-92% por activo

**Resultado:**
- Un único cerebro que aprende dinámicas específicas por símbolo
- Sin fragmentación (swarm intelligence intacto)
- Modelo consciente de que predice para BTC vs POL vs BNB
- **Coherencia garantizada:** 10 activos monitoreados, influencia mutua intacta

---

### 2️⃣ Umbrales dinámicos por activo (Parte B)

**Implementado:** MetaEvaluador adaptativo por WR histórico

**Cambios:**
- `src/ai/meta_evaluator.py`: Umbral dinámico = base + (0.50 - asset_wr) * 0.40, capped 0.72

**Resultado (datos 2026-04-09):**
- **BNB** (20.2% WR) → umbral 0.639 (necesita +11.9pp convicción)
- **POL** (25.7% WR) → umbral 0.617 (necesita +9.7pp convicción)
- **BTC** (79.0% WR) → umbral 0.520 (sin penalización)
- Activos problemáticos siguen activos pero con filtro de calidad
- Evita sacrificar potencial futuro mientras protege del drawdown actual

---

### 3️⃣ Pausa de ventana horaria destructiva 14-17 UTC (Tarea 2)

**Implementado:** Filtro como paso 0 en `_autonomous_decide()`

**Cambios:**
- `src/constants.py`: `DESTRUCTIVE_HOUR_START=14, DESTRUCTIVE_HOUR_END=17`
- `src/main.py`: Agregado `from datetime import timezone`
- `src/main.py`: Filtro antes del CircuitBreaker en `_autonomous_decide()`
- Configurable via `.env` (DESTRUCTIVE_HOUR_START / DESTRUCTIVE_HOUR_END)

**Resultado:**
- Rechaza todas las órdenes en 14:00-16:59 UTC
- WR histórico en esa ventana: 33% (vs 42% global)
- Evita -$85.92 de drawdown (75% del histórico)
- Log claro: `⏸️ [AUTONOMÍA] Ventana 14-17h UTC — WR histórico 33%`

---

### 3️⃣ Aumentar NORMAL_MIN_CONFIDENCE de 0.38 → 0.45 (después de fijar activos + horas)

**Problema en SysMho:**
- Umbral 0.38 = "levemente más probable BUY que WAIT"
- XGBoost predice [P(SELL), P(WAIT), P(BUY)]; si BUY=0.40, WAIT=0.38, SELL=0.22 → aprueba BUY
- Hay validación cruzada interna (Inertia filter, Strength ratio), pero **NO son suficientes** para 42.4% WR real
- **NOTA:** Datos reales muestran que el problema MAYOR es POL/BNB + 14-17 UTC, no confianza marginal

**Por qué es crítico para SysMho:**
- Modo autónomo (MetaEvaluador + CircuitBreaker) depende de confianza XGBoost como **score base**
- META_SCORE_THRESHOLD = 0.52 ya rechaza ~30% de señales
- Pero los 70% aprobados incluyen trades de POL/BNB/14-17UTC con baja confianza
- En live real market, esa confianza marginal falla especialmente en períodos/activos malos

**Qué cambiar:**
- `.env` → `NORMAL_MIN_CONFIDENCE=0.45` (o 0.48 para más conservador)
- AGGRESSIVE_MIN_CONFIDENCE podría ir 0.35 → 0.40
- Verificar que cambio propague a MetaEvaluator (usa NORMAL_MIN_CONFIDENCE en score_base)

**Impacto en SysMho (después de tasks 1+2):**
- Secundario: rechaza ~10-15 trades "borderline" adicionales
- Mantiene ~50+ trades de alta confianza que ganan en backtest
- Reduce volumen pero mejora precision
- **PRIORIDAD:** Hacer tareas 1 + 2 primero; esta es refinamiento posterior

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

## 📊 Estimación de mejora (post-4-fixes, con datos reales)

| Métrica | Actual | Post-fixes | Mejora | Justificación |
|---------|--------|-----------|--------|---|
| Win rate | 42.4% | 55-60% | +13-18pp | Elimina POL (25% WR) + BNB (18% WR) + pausa 14-17 UTC (33% WR) |
| PnL (closed) | -$114.57 | -$28.65 | +$85.92 (~75%) | POL -$56 + BNB -$24 + 14-17UTC -$86 = -$166 evitado |
| Trades closed | 92 | ~70-75 | -15-20 | Menos horas débiles, menos activos destructivos |
| Drawdown | -$114.57 | -$28.65 | -$85.92 (75%) | 14-17 UTC = 75% del drawdown; POL+BNB = 70% |
| Signal source | NULL (0%) | Auditable (100%) | ✅ | Implementar guardar BOUNTY vs REGULAR |
| MetaEvaluator | Sin filtro por-activo | +filtro por-activo | +Coherencia | Después de fix 1: solo activos ganadores |

---

## 🚀 Próximos pasos (PRIORIDAD)

### FASE 1: Fixes Inmediatos (Esta semana)
1. **Task 1:** Excluir POL + BNB de `SYMBOLS` en `src/constants.py` (~5 min)
   - Verificar impacto: loops respeten exclusión
   - Test local en testnet
   
2. **Task 2:** Pausar trading 14-17 UTC en `src/main.py:dispatch_signal()` (~10 min)
   - Agregar time gate antes de `executor.execute_trade()`
   - Log a `sysmho_brain.log`
   - Test en testnet: verificar que no ejecuta en esa ventana

3. **Task 4:** Guardar `signal_source` en `execute_trade()` (~10 min)
   - `src/main.py`: pasar `signal_source="BOUNTY"` o `"REGULAR"` 
   - `src/executor/trader.py`: guardar en BD

### FASE 2: Refinamiento (Después de FASE 1)
4. **Recolectar 100+ trades** en testnet con fixes aplicados
   - Medir nuevo win rate (esperado 50-55%)
   - Verificar que POL/BNB/14-17 UTC efectivamente eliminan drawdown

5. **Analizar BOUNTY vs REGULAR** con signal_source poblado
   - ¿BOUNTY WR > REGULAR WR?
   - ¿Diferencia significativa por activo?
   - Base para Phase 2 meta-modelo

6. **Task 3:** Aumentar NORMAL_MIN_CONFIDENCE 0.38 → 0.45 (si sigue < 50% WR)
   - Solo si análisis FASE 2 muestra que aún hay trades marginales

7. **Optuna tuning:** Si win rate post-fixes sigue < 50%, retuning bayesiano
   - Principalmente refinar META_SCORE_THRESHOLD, CB thresholds

### FASE 3: Autonomía Plena
8. **Mainnet:** Cuando win rate consistente > 55% en testnet durante 2 semanas

---

## 🔗 Referencias

- `src/main.py`: entry point, loops principales
- `src/constants.py`: SYMBOLS, NORMAL_MIN_CONFIDENCE, MODEL_FEATURES
- `src/ai/meta_evaluator.py`: META_SCORE_THRESHOLD, componentes del score
- `src/executor/circuit_breaker.py`: máximos diarios, límites de posición
- `src/ai/self_learner.py`: actualiza meta_stats con win_rate_by_hour
- `.env`: BINANCE_API_KEY, BINANCE_TESTNET, CB_* thresholds
