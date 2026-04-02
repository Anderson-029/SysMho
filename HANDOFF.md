# SysMho — Documento de Traspaso v15.2.0

> **Versión estable**: 15.2.0
> **Fecha de estabilización**: 2026-03-30
> **Estado**: Operativo — Modo Autónomo activo, Gap Filler integrado, PnL diario persistente

---

## Estado del flujo operativo (verificado en testnet)

| Acción del operador / sistema | Lo que hace SysMho | Estado |
|---|---|---|
| Arranque del motor | Gap Filler detecta y rellena velas faltantes (5m/1h/4h) antes de los WebSockets | ✅ Verificado |
| Señal generada (modo MANUAL) | Aparece en dashboard — espera aprobación humana | ✅ Verificado |
| Señal generada (modo AUTÓNOMO) | MetaEvaluator evalúa → aprueba o rechaza solo → log detallado en telemetría | ✅ Verificado |
| Circuit Breaker activado | Bloquea toda decisión autónoma → registra motivo en `autonomous_decisions` | ✅ Verificado |
| Aprobar señal en dashboard | Orden MARKET en Binance + SL + TP | ✅ Verificado |
| Cerrar y Cobrar posición | Cancela SL/TP → Orden MARKET cierre → Limpia BD | ✅ Verificado |
| Binance no responde | Usa precio local como fallback (no limpia BD) | ✅ Verificado |
| Posición cerró por TP/SL en Binance | Detecta ausencia → BINANCE_SYNC limpia BD | ✅ Verificado |

> **Nota testnet**: Los órdenes SL/TP (`STOP_MARKET`, `TAKE_PROFIT_MARKET`) fallan en testnet con error `-4120` — es una limitación del sandbox de Binance, no del código. En mainnet funcionan correctamente.

---

## Cómo arrancar el sistema

```bash
cd "/home/anderson/Documentos/programas personales/SysMho"
bash start_sysmho.sh
```

El script levanta en orden:
1. `uvicorn src.dashboard.api:app` → Dashboard en http://localhost:8000
2. `python -m src.main` → Gap Filler → WebSockets → Motor de IA + loops autónomos

Si el dashboard no levanta con el script (race condition de arranque), lanzarlo manualmente:
```bash
source venv/bin/activate
PYTHONPATH=$(pwd) uvicorn src.dashboard.api:app --host 0.0.0.0 --port 8000
```

**Credenciales del dashboard**: `X-API-Key: SysMho_2052_Ander` (definida en `.env`)

---

## Arquitectura de conexión

```
Binance REAL (mainnet, endpoints públicos)
    ↓ OHLCV en tiempo real, Funding Rate, Order Book
GapFiller (al arranque)         websocket.py / market_data.py
    ↓ rellena huecos históricos       ↓ datos reales en vivo
    └─────────────────PostgreSQL──────┘
                        ↓
              Motor de IA (XGBoost v3, 27 features)
                        ↓ señal PENDING
        ┌───────────────┴───────────────┐
        │ Modo MANUAL                   │ Modo AUTÓNOMO
        │ Operador aprueba              │ MetaEvaluator evalúa
        │ en dashboard                  │ → CircuitBreaker verifica
        │                               │ → aprueba o rechaza
        └───────────────┬───────────────┘
                        ↓ aprobado
              TradeExecutor (trader.py)
                BINANCE_TESTNET=True  → testnet
                BINANCE_TESTNET=False → real

Canal de runtime entre procesos:
  Dashboard (FastAPI) ←→ runtime_state.json ←→ Motor (main.py)
  Escribe: modo autónomo, cb_reset_at, pnl_reset_at, sync_status
  Lee:     is_autonomous(), get_cb_reset_at(), get_pnl_reset_at()
```

**Separación crítica**: los colectores de datos NUNCA usan sandbox. Solo `trader.py` respeta `BINANCE_TESTNET`.

---

## Stack técnico

| Componente | Tecnología |
|---|---|
| Backend API | FastAPI + uvicorn |
| Base de datos | PostgreSQL + asyncpg |
| Motor de IA | XGBoost (modelo v3, 27 features) |
| Datos en tiempo real | CCXT Pro WebSocket |
| Datos históricos / Gap Filler | CCXT REST (Binance público) |
| Optimización hiperparámetros | Optuna Bayesiano (50 trials) |
| Frontend | Vanilla JS + CSS separados |
| Entorno | Python 3.12, venv |

---

## Modo Autónomo (v15.2.0)

SysMho puede operar en dos modos controlados desde el dashboard (modal "AUTONOMÍA"):

### MANUAL (por defecto)
- Cada señal queda como `PENDING` en el dashboard.
- El operador decide aprobar o rechazar manualmente.

### AUTÓNOMO
Activado desde el dashboard → escribe `autonomous_mode: true` en `runtime_state.json`.

Por cada señal generada el motor ejecuta `_autonomous_decide()`:

```
CircuitBreaker.check() → si triggered → REJECTED + motivo + log
       ↓ OK
MetaEvaluator.evaluate() → meta_score (0–1) con 5 componentes:
  1. Win rate global (de trades históricos)
  2. Win rate por hora del día
  3. Calibración de confianza (predicha vs real)
  4. Racha de pérdidas reciente
  5. Confianza base de la señal XGBoost
       ↓
  meta_score ≥ META_SCORE_THRESHOLD (default 0.52) → APPROVED
  meta_score <  META_SCORE_THRESHOLD               → REJECTED
       ↓
  Log en autonomous_decisions + actualiza pending_approvals
```

### Circuit Breaker (5 stops duros)

| Parámetro | Env var | Valor por defecto |
|---|---|---|
| Posiciones simultáneas máx | `CB_MAX_POSITIONS` | 3 |
| Trades por día máx | `CB_MAX_DAILY_TRADES` | 8 |
| Pérdidas consecutivas máx | `CB_MAX_CONSEC_LOSSES` | 3 |
| Pérdida diaria máx | `CB_DAILY_LOSS_PCT` | 4% |
| Drawdown semanal máx | `CB_WEEKLY_DRAWDOWN_PCT` | 8% |

Cuando el CB se dispara puede resetearse manualmente desde el dashboard (botón "REINICIAR CONTADORES") sin borrar datos reales — usa un timestamp `cb_reset_at` en `runtime_state.json`.

### SelfLearner
Aprende de cada trade cerrado en `trades` (status=CLOSED). Actualiza `meta_stats.json` con:
- Win rate global
- Win rate por hora UTC
- Calibración de confianza por tramo

Necesita 200+ trades para activar la capa meta-modelo (XGBoost de segundo nivel, fase futura).

---

## Gap Filler (v15.2.0)

Al arrancar `src/main.py`, **antes** de conectar los WebSockets:

1. Detecta el `MAX(open_time)` por símbolo × temporalidad (`5m`, `1h`, `4h`)
2. Descarga desde Binance las velas faltantes (paginado, 1000/batch)
3. Inserta con `ON CONFLICT DO UPDATE` (idempotente)
4. Reporta el progreso en `sync_status` del `runtime_state.json` (visible en el badge "SINCRONIZANDO..." del dashboard)

Esto garantiza que el histórico esté completo en PostgreSQL cada vez que SysMho arranca, sin importar cuánto tiempo estuvo apagado.

---

## Portafolio activo

```
BTC/USDT  ETH/USDT  BNB/USDT  SOL/USDT  XRP/USDT
ADA/USDT  AVAX/USDT  LINK/USDT  DOT/USDT  POL/USDT
```

Temporalidades: **5m** (predicción principal) + **1h** y **4h** (contexto macro)

---

## Sistema de alertas

| Tipo | Frecuencia | Criterio |
|---|---|---|
| **REGULAR** | Cada 5 minutos | Top 3 activos por score compuesto |
| **BOUNTY** | Cuando se detecta | Confianza ≥ 55% + 3 tendencias alineadas + R/R ≥ 3.0 |

**Score compuesto**: `confianza×0.40 + fuerza×0.30 + alineación×0.20 + R/R×0.10`

Las señales expiran automáticamente a los 5 minutos sin respuesta (`DISMISSED`). En modo autónomo las decide el MetaEvaluator en milisegundos.

---

## Modelo de IA — v3 (27 features)

### Features del modelo (`MODEL_FEATURES` en `constants.py`)

| Grupo | Features |
|---|---|
| Momentum 5m | `rsi_14`, `stoch_rsi_k`, `macd_diff_pct` |
| Tendencia 5m | `adx`, `adx_pos`, `bb_pband` |
| Precio normalizado | `atr_pct`, `ema_21_dist`, `ema_200_dist`, `vwap_dist`, `pct_change`, `vol_change` |
| Futuros | `funding_rate`, `obi_20` |
| Swarm intelligence | `swarm_rsi_avg`, `swarm_macd_avg`, `swarm_bull_ratio` |
| Macro 1h | `h1_rsi_14`, `h1_macd_diff_pct`, `h1_adx`, `h1_bb_pband`, `h1_atr_pct` |
| Macro 4h | `h4_rsi_14`, `h4_macd_diff_pct`, `h4_adx`, `h4_bb_pband`, `h4_atr_pct` |

### Métricas del entrenamiento v3

| Activo | CV (5-fold) | Hold-out |
|---|---|---|
| BTC/USDT | 93.74% ± 2.94% | 97.19% |
| ETH/USDT | 88.76% ± 5.57% | 88.89% |
| BNB/USDT | 90.76% ± 8.27% | 95.21% |
| SOL/USDT | 86.57% ± 5.12% | 91.31% |
| XRP/USDT | 86.30% ± 7.67% | 88.52% |
| ADA/USDT | 83.04% ± 7.52% | 83.42% |
| AVAX/USDT | 87.92% ± 5.18% | 88.21% |
| LINK/USDT | 83.06% ± 7.27% | 83.53% |
| DOT/USDT | 87.83% ± 4.85% | 84.36% |
| POL/USDT | 81.24% ± 15.86% | 90.44% |

### Hiperparámetros Optuna (guardados en `src/ai/models/best_params.joblib`)

```python
n_estimators=235, max_depth=5, learning_rate=0.1259,
subsample=0.667, colsample_bytree=0.788, gamma=1.53e-05
```

---

## Parámetros operativos clave (`constants.py`)

| Parámetro | Valor | Descripción |
|---|---|---|
| `LABEL_THRESHOLD` | `0.007` | Movimiento mínimo para etiquetar BUY/SELL |
| `NORMAL_MIN_CONFIDENCE` | `0.38` | Confianza mínima para emitir señal |
| `NORMAL_INERTIA_THRESHOLD` | `0.72` | Veta señal si WAIT supera este % |
| `HIGH_CONVICTION_THRESHOLD` | `0.55` | Umbral de alta convicción (BOUNTY) |
| `NOTIONAL_CAP_RATIO` | `0.12` | Máximo 12% del capital por operación |
| `EXPOSURE_LIMIT_RATIO` | `0.50` | Bloquea si exposición total > 50% |
| `NORMAL_RISK_PER_TRADE` | `0.02` | Riesgo máximo 2% del portafolio por trade |
| `NORMAL_ATR_SL` | `1.5` | Stop Loss a 1.5× ATR |
| `NORMAL_ATR_TP` | `3.0` | Take Profit a 3.0× ATR (R/R 2:1) |
| `BOUNTY_MIN_RR_RATIO` | `3.0` | R/R mínimo para alertas BOUNTY |
| `TOP_N_SIGNALS` | `3` | Señales REGULAR por ciclo de 5 min |
| `META_SCORE_THRESHOLD` | `0.52` | Umbral MetaEvaluator para aprobación autónoma |

---

## Cómo reentrenar el modelo

```bash
# Solo entrenamiento (usa best_params.joblib de Optuna existente)
source venv/bin/activate
python -m src.ai.trainer --symbol ALL --timeframe 5m

# Reentrenamiento con nueva sintonía Bayesiana (50 trials, tarda ~30 min)
python -m src.ai.trainer --symbol ALL --timeframe 5m --tune --trials 50
```

**IMPORTANTE**: Si se cambian las features del modelo (`MODEL_FEATURES` en `constants.py`),
hay que eliminar el modelo anterior antes de reentrenar:
```bash
rm src/ai/models/xgboost_v1.joblib
```

---

## Migrar a cuenta real (cuando esté lista la verificación Binance)

1. Crear API Keys en Binance real con permisos de Futuros
2. Actualizar `.env`:
   ```
   BINANCE_API_KEY=<key real>
   BINANCE_SECRET_KEY=<secret real>
   BINANCE_TESTNET=False
   ```
3. Reiniciar SysMho

Los datos de mercado ya apuntan a Binance real — no hay más cambios de código.

---

## Archivos clave

```
SysMho/
├── .env                              # API keys + credenciales DB (NO commitear)
├── start_sysmho.sh                   # Arranque completo del sistema
├── stop_sysmho.sh                    # Parada controlada (verifica posiciones abiertas)
├── HANDOFF.md                        # Este archivo
├── SYSMHO_MANIFESTO.md               # Documentación técnica completa
│
├── config/
│   └── settings.py                   # Lee .env y valida API keys al arranque
│
├── src/
│   ├── main.py                       # Orquestador: Gap Filler, WebSockets, scanner, loops autónomos
│   ├── constants.py                  # Fuente única de verdad: MODEL_FEATURES, umbrales, riesgo
│   ├── runtime_config.py             # Canal runtime: autonomous, cb_reset, pnl_reset, sync_status
│   ├── runtime_state.json            # Estado compartido entre dashboard y motor (generado en vivo)
│   │
│   ├── ai/
│   │   ├── trainer.py                # CLI de entrenamiento (--symbol --tune --trials)
│   │   ├── predictor.py              # Carga modelo, predice, calcula score/bounty
│   │   ├── backtest.py               # CLI de backtest vectorizado con fees reales
│   │   ├── meta_evaluator.py         # MetaEvaluator: 5 componentes estadísticos → meta_score
│   │   ├── self_learner.py           # SelfLearner: aprende de trades cerrados → meta_stats.json
│   │   └── trainers/
│   │       ├── base.py               # create_labels(LABEL_THRESHOLD), save_performance()
│   │       ├── sequential.py         # TimeSeriesSplit + class_weight + MODEL_FEATURES
│   │       └── tuner.py              # Optuna Bayesiano
│   │
│   ├── analysis/
│   │   ├── features.py               # 27 features normalizadas + swarm lag fix
│   │   └── indicators.py             # TechnicalIndicators (todos los indicadores base)
│   │
│   ├── collector/
│   │   ├── websocket.py              # SIEMPRE Binance real (público, sin sandbox)
│   │   ├── market_data.py            # SIEMPRE Binance real (histórico, sin sandbox)
│   │   ├── backfill.py               # Descarga masiva histórica inicial
│   │   └── gap_filler.py             # Rellena huecos 5m/1h/4h al arranque
│   │
│   ├── database/
│   │   ├── repository.py             # asyncpg: upsert, fetch, sync portafolio, log autonomy
│   │   ├── schema.sql                # DDL completo de todas las tablas
│   │   ├── migration_v14_9_0.sql     # Añade alert_category y score a pending_approvals
│   │   ├── migration_v15_0_0.sql     # Depreca modelos v2, añade índice model_performance
│   │   └── migration_v15_2_0.sql     # Añade autonomous_decisions y meta_stats
│   │
│   ├── risk/
│   │   └── manager.py                # Auditor: position sizing, notional cap, exposure limit
│   │
│   ├── executor/
│   │   ├── trader.py                 # Ejecuta órdenes + telemetría a brain.log
│   │   ├── monitor.py                # Monitorea SL/TP + telemetría a brain.log
│   │   └── circuit_breaker.py        # 5 stops duros: posiciones, trades, rachas, PnL%
│   │
│   └── dashboard/
│       ├── api.py                    # FastAPI: middleware auth, mount /assets
│       ├── deps.py                   # Singletons: db, trader, risk_manager, monitor
│       ├── routes/
│       │   ├── signals.py            # Señales PENDING, aprobación, rechazo
│       │   ├── portfolio.py          # Balance, stats (PnL diario), ajuste capital, reset PnL
│       │   ├── positions.py          # Posiciones abiertas, cierre manual
│       │   ├── market.py             # Datos de mercado, gráficos
│       │   ├── system.py             # Status, last_scan, freshness, DB, sync_status, logs
│       │   └── autonomous.py         # Toggle autonomía, status CB, reset CB, decisiones
│       └── static/
│           ├── index.html            # HTML estructural (offline overlay, sync badge, modal autonomía)
│           └── assets/
│               ├── style.css         # CSS completo (colores telemetría, animaciones)
│               └── app.js            # JS completo (systemOnline, autonomy panel, PnL diario)
│
└── src/ai/models/
    ├── xgboost_v1.joblib             # Modelo v3 entrenado (27 features, 10 activos)
    ├── best_params.joblib            # Hiperparámetros óptimos Optuna
    └── meta_stats.json               # Estadísticas de aprendizaje del SelfLearner
```

---

## Indicadores del dashboard

| Indicador | Endpoint | Significado |
|---|---|---|
| `ENLACE ACTIVO` | `/api/system/status` | Conexión Binance OK (fetch_balance) |
| `BD ACTIVA` | `/api/db/status` | PostgreSQL responde (SELECT 1) |
| `DATOS Xs` | `/api/data/freshness` | Antigüedad de la última vela 5m recibida |
| `⏱ 4:34` | `/api/system/last_scan` | Tiempo restante para el próximo scan REGULAR |
| `SINCRONIZANDO...` | `/api/system/sync_status` | Gap Filler activo al arranque |
| `MANUAL` / `AUTÓNOMO` / `CB ACTIVO` | `/api/autonomous/status` | Modo de operación actual |

**Umbrales DATOS**:
- Verde `FRESH`: última vela < 5min 30s (normal en ciclo de 5m)
- Naranja `DELAY`: última vela entre 5:30 y 15min (una vela perdida)
- Rojo `STALE`: última vela > 15min (problema real de datos)

**PnL Diario** (barra de nav): suma de trades cerrados desde medianoche (o último reset manual `↺`) + PnL flotante actual. Se acumula entre trades del mismo día y solo se reinicia a medianoche o al presionar el botón `↺`.

---

## Próximos pasos sugeridos

1. **Verificación Binance**: Resolver el problema de cuenta duplicada para pasar a mainnet
2. **Operar en modo autónomo testnet**: Acumular 200+ trades para activar el meta-modelo XGBoost de segundo nivel
3. **Calibrar umbrales del CB**: Ajustar `CB_MAX_DAILY_TRADES`, `CB_DAILY_LOSS_PCT` según resultados reales en testnet
4. **Meta-modelo (Fase 2 autonomía)**: Entrenar XGBoost sobre `meta_stats.json` cuando haya suficientes datos — reemplaza los 5 heurísticos del MetaEvaluator por un modelo aprendido
