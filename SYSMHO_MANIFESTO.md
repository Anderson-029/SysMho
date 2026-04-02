# SYSMHO — MANIFIESTO MAESTRO

> **Versión**: 15.2.0
> **Última actualización**: 2026-03-30
> **Estado**: Operativo — Autonomía + Circuit Breaker + Gap Filler + PnL diario persistente

---

## Índice

1. [¿Qué es SysMho?](#1-qué-es-sysmho)
2. [Arquitectura de Conexión](#2-arquitectura-de-conexión)
3. [Estructura del Proyecto](#3-estructura-del-proyecto)
4. [Base de Datos](#4-base-de-datos)
5. [Colector de Datos y Gap Filler](#5-colector-de-datos-y-gap-filler)
6. [Motor de Análisis Técnico](#6-motor-de-análisis-técnico)
7. [Motor de IA — XGBoost v3](#7-motor-de-ia--xgboost-v3)
8. [Sistema de Alertas](#8-sistema-de-alertas)
9. [Auditoría de Riesgos](#9-auditoría-de-riesgos)
10. [Modo Autónomo — MetaEvaluator + Circuit Breaker](#10-modo-autónomo--metaevaluator--circuit-breaker)
11. [SelfLearner — Aprendizaje Continuo](#11-selflearner--aprendizaje-continuo)
12. [Ejecutor de Órdenes](#12-ejecutor-de-órdenes)
13. [Monitor de Posiciones](#13-monitor-de-posiciones)
14. [Centro de Comando (Dashboard)](#14-centro-de-comando-dashboard)
15. [Backtest](#15-backtest)
16. [Flujo Completo de una Operación](#16-flujo-completo-de-una-operación)
17. [Parámetros de Configuración](#17-parámetros-de-configuración)
18. [Crónica de Versiones](#18-crónica-de-versiones)

---

## 1. ¿Qué es SysMho?

SysMho es un sistema de trading algorítmico para futuros perpetuos de criptomonedas. Combina análisis técnico multi-temporal, inteligencia de enjambre, un modelo XGBoost entrenado secuencialmente en 10 activos, control de riesgo matemático estricto, y un motor de toma de decisiones autónomo con aprendizaje continuo.

Puede operar en dos modos:

- **MANUAL**: cada señal requiere aprobación del operador (Human-in-the-Loop).
- **AUTÓNOMO**: el MetaEvaluator evalúa cada señal estadísticamente y decide por su cuenta. El Circuit Breaker actúa como red de seguridad ante rachas adversas.

El modo se cambia en tiempo real desde el dashboard sin reiniciar ningún proceso.

### Portafolio activo

```
BTC/USDT  ETH/USDT  BNB/USDT  SOL/USDT  XRP/USDT
ADA/USDT  AVAX/USDT  LINK/USDT  DOT/USDT  POL/USDT
```

### Temporalidades

| Temporalidad | Uso |
|---|---|
| **5m** | Predicción principal, señales de entrada |
| **1h** | Contexto macro inyectado como features |
| **4h** | Contexto estructural de largo plazo |

---

## 2. Arquitectura de Conexión

```
┌─────────────────────────────────────────────────────┐
│              BINANCE REAL (mainnet)                  │
│         endpoints públicos — sin autenticación       │
│    OHLCV en vivo · Histórico · Funding Rate · OBI    │
└──────────────────────┬──────────────────────────────┘
                       │
         ┌─────────────▼─────────────┐
         │   GapFiller (al arranque)  │  ← detecta y rellena 5m/1h/4h
         └─────────────┬─────────────┘
                       │ + WebSockets en vivo
         ┌─────────────▼─────────────┐
         │    PostgreSQL (local)      │
         │  ~6.5M+ velas históricas   │
         └─────────────┬─────────────┘
                       │
         ┌─────────────▼─────────────┐
         │    Motor XGBoost v3        │
         │   27 features limpias      │
         │   TimeSeriesSplit CV       │
         └─────────────┬─────────────┘
                       │ señal PENDING
        ┌──────────────┴──────────────┐
        │ Modo MANUAL                  │ Modo AUTÓNOMO
        │ dashboard → operador decide  │ MetaEvaluator → meta_score
        │                              │ CircuitBreaker → 5 stops duros
        │                              │ aprueba o rechaza en ms
        └──────────────┬──────────────┘
                       │ aprobado
         ┌─────────────▼─────────────┐
         │    TradeExecutor           │
         │  TESTNET=True  → testnet   │
         │  TESTNET=False → real      │
         └────────────────────────────┘

Canal runtime entre procesos (sin reiniciar):
  Dashboard ←→ runtime_state.json ←→ Motor
```

**Regla fundamental**: Los colectores de datos (`websocket.py`, `market_data.py`, `gap_filler.py`) NUNCA usan sandbox. Solo `trader.py` respeta `BINANCE_TESTNET`.

---

## 3. Estructura del Proyecto

```
SysMho/
├── .env                          # API keys, credenciales BD (no commitear)
├── start_sysmho.sh               # Arranque completo
├── stop_sysmho.sh                # Parada controlada (verifica posiciones)
├── HANDOFF.md                    # Guía de traspaso y referencia rápida
├── SYSMHO_MANIFESTO.md           # Este documento
├── requirements.txt              # Dependencias Python
│
├── config/
│   └── settings.py               # Lee .env, valida keys, expone DATABASE_URL
│
└── src/
    ├── main.py                   # Orquestador: Gap Filler, WebSockets, scanner, loops
    ├── constants.py              # Fuente única de verdad (MODEL_FEATURES, umbrales)
    ├── runtime_config.py         # Canal runtime: autonomous, cb_reset, pnl_reset, sync
    ├── runtime_state.json        # Estado compartido entre procesos (generado en vivo)
    │
    ├── ai/
    │   ├── trainer.py            # CLI orquestador de entrenamiento
    │   ├── predictor.py          # Carga modelo, predict(), score(), is_bounty()
    │   ├── backtest.py           # CLI de backtest vectorizado con fees reales
    │   ├── meta_evaluator.py     # 5 componentes estadísticos → meta_score (0–1)
    │   ├── self_learner.py       # Aprende de trades cerrados → meta_stats.json
    │   └── trainers/
    │       ├── base.py           # create_labels(), save_performance() per-clase
    │       ├── sequential.py     # TimeSeriesSplit + class_weight + MODEL_FEATURES
    │       └── tuner.py          # Optuna Bayesiano (50 trials)
    │
    ├── analysis/
    │   ├── features.py           # FeatureEngineer: 27 features, swarm con lag fix
    │   └── indicators.py         # TechnicalIndicators.add_all_indicators()
    │
    ├── collector/
    │   ├── websocket.py          # BinanceWebSocket: velas en vivo + sentimiento
    │   ├── market_data.py        # MarketDataCollector: histórico OHLCV
    │   ├── backfill.py           # Descarga masiva inicial
    │   └── gap_filler.py         # Rellena huecos 5m/1h/4h antes de iniciar WS
    │
    ├── database/
    │   ├── repository.py         # DatabaseRepository: asyncpg pool + log autonomy
    │   ├── schema.sql            # DDL completo
    │   ├── migration_v14_9_0.sql # alert_category, score en pending_approvals
    │   ├── migration_v15_0_0.sql # Depreca modelos v2
    │   └── migration_v15_2_0.sql # autonomous_decisions, meta_stats
    │
    ├── risk/
    │   └── manager.py            # RiskManager: position sizing, exposure limit
    │
    ├── executor/
    │   ├── trader.py             # TradeExecutor: órdenes market + SL/TP
    │   ├── monitor.py            # Monitor de posiciones abiertas
    │   └── circuit_breaker.py    # 5 stops duros de seguridad autónoma
    │
    └── dashboard/
        ├── api.py                # FastAPI app: middleware auth, mount assets
        ├── deps.py               # Singletons compartidos
        ├── routes/
        │   ├── signals.py        # Señales PENDING, aprobación, rechazo
        │   ├── portfolio.py      # Balance, stats PnL diario, ajuste capital, reset PnL
        │   ├── positions.py      # Posiciones abiertas, cierre manual
        │   ├── market.py         # Datos de mercado, gráficos
        │   ├── system.py         # Status, last_scan, freshness, DB, sync_status, logs
        │   └── autonomous.py     # Toggle autonomía, CB status, reset CB, decisiones
        └── static/
            ├── index.html        # HTML: offline overlay, sync badge, modal autonomía
            └── assets/
                ├── style.css     # CSS: colores telemetría, animaciones offline
                └── app.js        # JS: systemOnline, autonomy panel, PnL diario
```

---

## 4. Base de Datos

**PostgreSQL** local. Pool de conexiones asyncpg (no ORM).

### Tablas principales

| Tabla | Contenido |
|---|---|
| `market_data` | OHLCV + ATR-14 por símbolo/timeframe/timestamp |
| `sentiment_data` | Funding rate, open interest, OBI por símbolo |
| `pending_approvals` | Señales esperando decisión (manual o autónoma) |
| `positions` | Posiciones abiertas activas |
| `trades` | Historial completo de operaciones ejecutadas |
| `portfolio` | Snapshots del balance (sincronización cada 5 min) |
| `risk_log` | Log de auditorías del RiskManager |
| `model_performance` | Métricas de precisión por activo y versión |
| `autonomous_decisions` | Log de cada decisión autónoma: meta_score, razones, CB |
| `meta_stats` | Estadísticas de aprendizaje por símbolo, hora y dirección |

### Canal runtime (`runtime_state.json`)

Archivo JSON compartido entre el dashboard y el motor. Se escribe atómicamente (tmp + rename). Campos:

| Campo | Escribe | Lee | Propósito |
|---|---|---|---|
| `autonomous_mode` | Dashboard | Motor | Modo manual/autónomo |
| `cb_reset_at` | Dashboard | Motor | Reset de contadores del Circuit Breaker |
| `pnl_reset_at` | Dashboard | Dashboard | Reset del contador de PnL diario |
| `sync_status` / `sync_detail` | Motor | Dashboard | Progreso del Gap Filler |

---

## 5. Colector de Datos y Gap Filler

### WebSocket en tiempo real (`websocket.py`)

Conecta a **Binance real** (mainnet, sin auth, sin sandbox) vía CCXT Pro.

Por cada símbolo abre 3 streams simultáneos (5m, 1h, 4h) más:
- **Sensor Institucional** (`_keep_sentiment_alive`): Funding Rate + Open Interest cada 60s
- **Radar de Liquidez** (`_monitor_order_book`): Order Book Imbalance (OBI) a 20 niveles cada 5s

### Histórico (`market_data.py`)

Descarga OHLCV histórico desde Binance real (endpoint público). Usado en backfill inicial y por el entrenador.

### Gap Filler (`gap_filler.py`)

Se ejecuta **automáticamente al arrancar** `main.py`, antes de iniciar los WebSockets.

**Flujo**:
1. Para cada símbolo × temporalidad (`5m`, `1h`, `4h`) consulta `MAX(open_time)` en PostgreSQL
2. Si el hueco es ≥ 2 velas (umbral para evitar falsos positivos por la vela actual incompleta), descarga desde Binance vía CCXT REST paginado (1000 velas/batch, 0.25s de pausa)
3. Inserta con `ON CONFLICT DO UPDATE` — 100% idempotente, seguro de re-ejecutar
4. Reporta progreso en `sync_status` → visible como badge "SINCRONIZANDO..." en el dashboard
5. Al terminar: `sync_status = 'idle'` y el badge desaparece

**Impacto**: garantiza que el histórico de PostgreSQL esté completo en cada arranque. El modelo XGBoost y el backtest siempre trabajan con datos continuos sin importar cuánto tiempo estuvo apagado SysMho.

---

## 6. Motor de Análisis Técnico

`TechnicalIndicators.add_all_indicators()` calcula sobre cada DataFrame OHLCV:

| Indicador | Columnas generadas |
|---|---|
| RSI 14 | `rsi_14` |
| MACD | `macd`, `macd_signal`, `macd_diff` |
| Bollinger Bands | `bb_high`, `bb_low`, `bb_mid`, `bb_pband` |
| EMAs | `ema_9`, `ema_21`, `ema_50`, `ema_200` |
| ATR 14 | `atr_14` |
| VWAP 14 | `vwap` |
| ADX | `adx`, `adx_pos`, `adx_neg` |
| StochRSI | `stoch_rsi_k`, `stoch_rsi_d` |
| Williams %R | `williams_r` |

De estos, el modelo usa los **27 features** definidos en `MODEL_FEATURES` (normalizados, sin redundancia).

---

## 7. Motor de IA — XGBoost v3

### Pipeline de entrenamiento

1. **Etiquetado** (`create_labels`): `LABEL_THRESHOLD=0.007` — solo etiqueta BUY/SELL si la siguiente vela mueve ≥0.7%.

2. **Features normalizadas** (27 features en `MODEL_FEATURES`):
   - Indicadores como porcentaje del precio (`atr_pct`, `ema_21_dist`, `vwap_dist`)
   - Swarm Intelligence con lag de 1 período para evitar sesgo futuro
   - Contexto macro 1h y 4h normalizado

3. **TimeSeriesSplit (5 folds)**: nunca entrena con datos del futuro.

4. **Class weights balanceados**: `compute_sample_weight('balanced')` compensa el desbalance natural.

5. **Aprendizaje incremental**: asimila un activo a la vez, transfiriendo conocimiento mediante `xgb_model=booster`.

6. **Optuna Bayesiano**: 50 trials. Parámetros guardados en `best_params.joblib`.

### Swarm Intelligence

- `swarm_rsi_avg`: RSI promedio de los otros 9 activos
- `swarm_macd_avg`: MACD promedio de los otros 9 activos
- `swarm_bull_ratio`: fracción de activos con precio > EMA21
- Lag de 1 período (`shift(1)`) para evitar sesgo hacia el futuro

---

## 8. Sistema de Alertas

### REGULAR (cada 5 minutos)

El escáner evalúa los 10 activos simultáneamente y selecciona el **Top 3** por score compuesto:

```
score = confianza×0.40 + fuerza×0.30 + alineación_tendencias×0.20 + R/R×0.10
```

### BOUNTY (alta convicción, sin horario fijo)

Se genera cuando se cumplen los 3 criterios simultáneamente:
- Confianza ≥ 55%
- Tendencias 5m + 1h + 4h alineadas (3/3)
- Ratio R/R ≥ 3.0

### Timeout

Las señales sin decisión expiran a los **5 minutos** (`DISMISSED`). En modo autónomo se decide en milisegundos.

---

## 9. Auditoría de Riesgos

`RiskManager` audita cada señal antes de presentarla (manual) o ejecutarla (autónomo):

| Regla | Acción |
|---|---|
| Señal WAIT | Rechazada automáticamente |
| ATR = 0 | Rechazada (volatilidad nula) |
| Notional < $6 USDT | Escala al mínimo si hay margen, sino rechaza |
| Notional > 12% del capital | Recorta al cap |
| Exposición total > 50% | Rechazada |

**Cálculo de SL/TP**:
- `stop_loss = precio ± (ATR × 1.5)`
- `take_profit = precio ± (ATR × 3.0)`
- Escudo mínimo: SL de LONG no puede estar por debajo del 90% del precio de entrada

---

## 10. Modo Autónomo — MetaEvaluator + Circuit Breaker

El modo autónomo permite que SysMho decida y ejecute operaciones sin intervención humana. Se activa/desactiva desde el modal "AUTONOMÍA" del dashboard. El estado persiste en `runtime_state.json`.

### MetaEvaluator (`meta_evaluator.py`)

Para cada señal calcula un `meta_score` (0–1) promediando 5 componentes:

| Componente | Fuente de datos | Qué mide |
|---|---|---|
| Win rate global | `meta_stats.json` | Historial general del sistema |
| Win rate por hora UTC | `meta_stats.json` | Rendimiento en la hora actual del día |
| Calibración de confianza | `meta_stats.json` | Si la confianza predicha = confianza real |
| Racha de pérdidas | Últimos 10 trades | Protección ante rachas adversas |
| Confianza base XGBoost | `win_probability` de la señal | Calidad de la predicción base |

Si `meta_score ≥ META_SCORE_THRESHOLD` (default `0.52`) → **APPROVED** → se ejecuta la operación.
Si `meta_score < META_SCORE_THRESHOLD` → **REJECTED** → se descarta la señal.

Toda decisión se registra en la tabla `autonomous_decisions` con todos los razonamientos.

### Circuit Breaker (`circuit_breaker.py`)

Se verifica **antes** del MetaEvaluator. Si se activa, bloquea toda decisión autónoma:

| Stop | Variable de entorno | Default |
|---|---|---|
| Posiciones abiertas simultáneas | `CB_MAX_POSITIONS` | 3 |
| Trades ejecutados en el día | `CB_MAX_DAILY_TRADES` | 8 |
| Pérdidas consecutivas | `CB_MAX_CONSEC_LOSSES` | 3 |
| Pérdida diaria acumulada | `CB_DAILY_LOSS_PCT` | 4% |
| Drawdown semanal acumulado | `CB_WEEKLY_DRAWDOWN_PCT` | 8% |

**Reset del Circuit Breaker**: el botón "REINICIAR CONTADORES" del dashboard escribe un nuevo `cb_reset_at` en `runtime_state.json`. A partir de ese timestamp, `get_daily_stats()` solo cuenta trades posteriores, efectivamente reiniciando los contadores sin borrar ningún dato real.

### Flujo autónomo completo

```
Señal PENDING generada por el scanner
        ↓
is_autonomous() → lee runtime_state.json en vivo
        ↓ True
get_daily_stats() → trades, PnL%, racha, posiciones abiertas
        ↓
CircuitBreaker.check() → triggered? → REJECTED + motivo
        ↓ OK
MetaEvaluator.evaluate(señal, trades_recientes)
        ↓
meta_score calculado + lista de razones
        ↓
log_autonomous_decision() → INSERT en autonomous_decisions
        ↓
UPDATE pending_approvals → status: APPROVED / REJECTED
        ↓ APPROVED
TradeExecutor.execute_signal() → orden en Binance
```

Telemetría en `sysmho_brain.log` con separadores `══` para cada bloque de decisión.

---

## 11. SelfLearner — Aprendizaje Continuo

`self_learner.py` se ejecuta en loop (`_learning_loop` en `main.py`) y procesa trades cerrados:

1. Consulta `trades WHERE status='CLOSED' AND id > last_processed_id`
2. Para cada trade llama `self_learner.update(trade)`:
   - Actualiza win rate global
   - Actualiza win rate por hora UTC del cierre
   - Actualiza calibración de confianza por tramo (0–40%, 40–55%, 55–70%, 70–100%)
3. Persiste en `meta_stats.json` (archivo en `src/ai/models/`)
4. Log de win rate global en `sysmho_brain.log` cada ciclo

### Roadmap del SelfLearner

| Fase | Condición | Descripción |
|---|---|---|
| **Actual** | Cualquier cantidad de trades | 5 heurísticos estadísticos en MetaEvaluator |
| **Fase 2** | ≥ 200 trades cerrados | Meta-modelo XGBoost entrenado sobre `meta_stats.json` |

Con 200+ trades, el MetaEvaluator puede reemplazar los heurísticos por un modelo aprendido que capture patrones no lineales entre confianza, hora, símbolo y resultado.

---

## 12. Ejecutor de Órdenes

`trader.py` ejecuta las órdenes aprobadas:

1. Verifica balance disponible
2. Normaliza cantidad y precio con precisión del exchange
3. Orden `MARKET` de entrada
4. Orden `STOP_MARKET` (SL)
5. Orden `TAKE_PROFIT_MARKET` (TP)
6. Registro contable en BD (`trades` + `positions`)
7. Actualización del portafolio

**Modo**: controlado por `BINANCE_TESTNET` en `.env`.

**Telemetría en tiempo real**: cada evento crítico se escribe directamente en `sysmho_brain.log`:
- Orden disparada → confirmación con ID de Binance
- SL/TP colocados o fallo con motivo exacto
- Cierre enviado → confirmado con ID
- Cualquier error fatal con el mensaje completo de Binance

> **Nota testnet**: `STOP_MARKET` y `TAKE_PROFIT_MARKET` no están soportados en el testnet de Binance (error `-4120`). El sistema lo registra como advertencia y continúa. En mainnet funcionan sin cambios.

---

## 13. Monitor de Posiciones

`monitor.py` vigila las posiciones abiertas cada segundo. Maneja tres escenarios:

| `get_active_positions_details()` | Significado | Acción |
|---|---|---|
| `{sym: datos}` | Binance confirma activa | Actualiza PnL con datos reales |
| `{}` | Binance OK, sin posición | `BINANCE_SYNC`: limpia BD (cerró por TP/SL) |
| `None` | Binance no respondió | Usa precio local como fallback, NO limpia BD |

**Cierre manual** (`manual_close_position`):
1. Consulta estado en Binance
2. Si activa: cancela SL/TP → orden de cierre a mercado → limpia BD
3. Si ya cerrada: solo limpia BD (`BINANCE_SYNC`)
4. Si Binance no responde: aborta (no deja posición zombie)

---

## 14. Centro de Comando (Dashboard)

**URL**: http://localhost:8000
**Auth**: header `X-API-Key: SysMho_2052_Ander`

### Secciones

| Sección | Función |
|---|---|
| Lockscreen | Protección al arranque — evita operaciones accidentales |
| Monitor de Predicciones | Señales PENDING (BOUNTY primero, luego REGULAR por score) |
| Historial de Autorizadas | Señales aprobadas/rechazadas anteriores |
| Posiciones Abiertas | Estado en tiempo real con PnL unrealized + cierre manual |
| Telemetría Neuronal | Log en vivo con colores: naranja=CB, amarillo=autonomía, verde=ejecución |
| Capital Operativo | Balance sincronizado con Binance |

### Indicadores de estado (barra superior)

| Indicador | Endpoint | Frecuencia |
|---|---|---|
| `ENLACE ACTIVO/RECONECTANDO` | `/api/system/status` | Cada 3s |
| `BD ACTIVA/DESCONECTADA` | `/api/db/status` | Cada 5s |
| `DATOS Xs / DELAY / STALE` | `/api/data/freshness` | Cada 10s |
| `⏱ MM:SS` (próximo scan) | `/api/system/last_scan` | Cada 30s + en vivo |
| `SINCRONIZANDO...` | `/api/system/sync_status` | Cada 3s |
| `MANUAL` / `AUTÓNOMO` / `CB ACTIVO` | `/api/autonomous/status` | Cada 10s |

**PnL Diario** (barra de nav): suma de trades cerrados desde medianoche (o `pnl_reset_at`) + PnL flotante actual. No se reinicia al cerrar un trade — solo a medianoche o al presionar `↺`.

### Detección de sistema offline

Cuando el motor o la API no responden:
- Todos los pollers se detienen (`systemOnline = false`)
- Se muestra un overlay "SYSMHO OFFLINE" con animación de pulso
- Al reconectarse: se eliminan el overlay y se recargan todos los datos

### Modal de Autonomía

Accesible desde el badge de modo en el nav. Contiene:
- Estado del modo actual y del Circuit Breaker
- Métricas del día (trades, PnL%, racha de pérdidas)
- Estadísticas del SelfLearner
- Botones ACTIVAR / MODO MANUAL
- Botón REINICIAR CONTADORES (reset CB sin borrar datos)
- Historial de las últimas decisiones autónomas

### Colores de telemetría

| Color | Clase CSS | Evento |
|---|---|---|
| Naranja | `log-cb` | `[CIRCUIT BREAKER]`, `🛑` |
| Amarillo | `log-auto` | `[AUTONOMÍA]`, `🤖`, `📈`, `🖐` |
| Verde bold | `log-exec` | órdenes ejecutadas, `✅` |

---

## 15. Backtest

`src/ai/backtest.py` mide el rendimiento histórico real del modelo con fees de Binance incluidos.

```bash
python -m src.ai.backtest [--symbol X] [--min-confidence 0.38] [--limit 50000] [--save file.csv]
```

**Metodología**: carga histórico de PostgreSQL → `predict_proba` en batch vectorizado → simulación forward (288 velas = 24h) → PnL neto con fees reales.

| Resultado | Fee aplicado |
|---|---|
| WIN | 0.06% (0.04% taker entrada + 0.02% maker TP) |
| LOSS / TIMEOUT | 0.08% (0.04% taker entrada + 0.04% taker SL) |

**Referencia** (50k velas, ~5.8 meses, conf ≥ 38%): Win Rate 58.2% · PF 2.12× · Hold 1.3h

---

## 16. Flujo Completo de una Operación

### Modo MANUAL (verificado en testnet)

```
1.  WebSocket recibe vela de BTC/USDT (5m) → guarda en DB
2.  Scanner 5m (cada 5 min) evalúa los 10 activos en paralelo
3.  FeatureEngineer construye DataFrame con 27 features
4.  XGBoost predice → confidence 67%, BUY
5.  Predictor calcula score=0.82, is_bounty=False
6.  RiskManager audita → aprobada, SL=$83,200, TP=$84,800, qty=0.0012 BTC
7.  Señal guardada en pending_approvals como REGULAR, score=0.82
8.  Dashboard muestra señal al operador
9.  Operador presiona APROBAR
10. TradeExecutor ejecuta → orden MARKET + SL + TP en testnet
11. BD registra trade y posición
12. Monitor.py vigila SL/TP cada 1s hasta cierre
```

### Modo AUTÓNOMO

```
1–7. Igual que modo manual
8.   _autonomous_decide() llamado por _handle_pending_approval()
9.   CircuitBreaker.check() → OK (posiciones<3, trades<8, racha<3, PnL>-4%)
10.  MetaEvaluator.evaluate() → meta_score=0.61 > 0.52 → APPROVED
11.  log_autonomous_decision() → INSERT en autonomous_decisions
12.  UPDATE pending_approvals → status=APPROVED
13.  TradeExecutor.execute_signal() → orden MARKET en Binance
14.  SelfLearner aprende del resultado cuando el trade cierra
```

---

## 17. Parámetros de Configuración

### IA y entrenamiento (`src/constants.py`)

| Parámetro | Valor | Descripción |
|---|---|---|
| `LABEL_THRESHOLD` | `0.007` | Movimiento mínimo 0.7% para etiquetar |
| `NORMAL_MIN_CONFIDENCE` | `0.38` | Confianza mínima de señal |
| `NORMAL_INERTIA_THRESHOLD` | `0.72` | Veta señal si WAIT > 72% |
| `HIGH_CONVICTION_THRESHOLD` | `0.55` | Umbral alta convicción |
| `MODEL_FEATURES` | 27 items | Lista exacta de features del modelo |

### Alertas

| Parámetro | Valor | Descripción |
|---|---|---|
| `TOP_N_SIGNALS` | `3` | Señales REGULAR por ciclo |
| `SIGNAL_SCAN_INTERVAL_SECONDS` | `300` | Ciclo scanner (5 min) |
| `BOUNTY_CONFIDENCE_THRESHOLD` | `0.55` | Confianza mínima BOUNTY |
| `BOUNTY_TREND_ALIGNMENT_REQUIRED` | `3` | Tendencias alineadas (5m+1h+4h) |
| `BOUNTY_MIN_RR_RATIO` | `3.0` | R/R mínimo BOUNTY |
| `PENDING_SIGNAL_TIMEOUT_SECONDS` | `300` | Expiración señal sin respuesta |

### Riesgo

| Parámetro | Valor | Descripción |
|---|---|---|
| `NORMAL_RISK_PER_TRADE` | `0.02` | 2% del capital por operación |
| `NORMAL_ATR_SL` | `1.5` | SL a 1.5× ATR |
| `NORMAL_ATR_TP` | `3.0` | TP a 3.0× ATR |
| `NOTIONAL_CAP_RATIO` | `0.12` | Máximo 12% del capital por trade |
| `EXPOSURE_LIMIT_RATIO` | `0.50` | Bloqueo si exposición > 50% |
| `MIN_NOTIONAL_USDT` | `6.0` | Mínimo Binance (5 USDT + margen) |

### Autonomía (variables de entorno en `.env`)

| Variable | Default | Descripción |
|---|---|---|
| `META_SCORE_THRESHOLD` | `0.52` | Umbral MetaEvaluator para aprobar |
| `AUTONOMOUS_MODE` | `false` | Modo inicial (se sobreescribe con runtime_state.json) |
| `CB_MAX_POSITIONS` | `3` | Posiciones simultáneas máx |
| `CB_MAX_DAILY_TRADES` | `8` | Trades por día máx |
| `CB_MAX_CONSEC_LOSSES` | `3` | Pérdidas consecutivas máx |
| `CB_DAILY_LOSS_PCT` | `0.04` | Pérdida diaria máx (4%) |
| `CB_WEEKLY_DRAWDOWN_PCT` | `0.08` | Drawdown semanal máx (8%) |

---

## 18. Crónica de Versiones

### v15.2.0 (2026-03-30) — Versión estable actual
- **Modo Autónomo**: MetaEvaluator evalúa cada señal con 5 componentes estadísticos (WR global, WR horario, calibración, racha, confianza base). Umbral configurable via `META_SCORE_THRESHOLD`
- **Circuit Breaker**: 5 stops duros (posiciones, trades/día, rachas, pérdida diaria%, drawdown semanal%). Reset manual desde dashboard via timestamp `cb_reset_at`
- **SelfLearner**: aprende de trades cerrados en tiempo real → `meta_stats.json`. Base para meta-modelo XGBoost (Fase 2, con 200+ trades)
- **Gap Filler**: al arrancar detecta y rellena huecos en 5m/1h/4h antes de iniciar WebSockets. Progreso visible en badge "SINCRONIZANDO..." del dashboard
- **Canal runtime**: `runtime_state.json` permite cambiar modo autónomo, resetear CB y PnL sin reiniciar ningún proceso
- **PnL Diario persistente**: el PnL del nav acumula todos los trades del día. Solo se reinicia a medianoche o manualmente con botón `↺`. No se borra al cerrar cada trade
- **Detección offline del dashboard**: si SysMho se apaga, todos los pollers se congelan y se muestra overlay "SYSMHO OFFLINE". Al reconectarse todo se reactiva
- **Telemetría coloreada**: naranja para CB, amarillo para autonomía, verde para ejecuciones
- **Fix Conf: 0.0%**: `pending_approvals` usa `win_probability` (no `confidence`) y `side` (no `direction`)
- **Fix toggle autonomía**: el motor ya no lee `os.environ` — usa `is_autonomous()` que lee `runtime_state.json` en cada decisión
- **Tabla `autonomous_decisions`**: log completo de cada decisión autónoma con meta_score, razones y estado del CB

### v15.1.0 (2026-03-29)
- Ejecución end-to-end verificada: apertura y cierre de posiciones confirmados en testnet Binance
- Telemetría de órdenes: `trader.py` y `monitor.py` escriben directamente al log neuronal
- Fix `ReduceOnly` (-2022): si Binance rechaza con "posición ya cerrada", se limpia la BD
- Fix doble cierre: botón "Cerrar y Cobrar" se deshabilita al primer clic
- Fix sincronización Binance/BD: `get_active_positions_details()` retorna `None` vs `{}` correctamente
- Backtest vectorizado con fees reales, Win Rate 58.2%, PF 2.12×
- Dashboard: botón BD activa, frescura de datos DATOS/DELAY/STALE, cronómetro sincronizado

### v15.0.0 (2026-03-29)
- Pipeline ML rediseñado: 27 features limpias (de 65), todas normalizadas
- TimeSeriesSplit (5-fold): validación temporal correcta
- Class weights balanceados: compensa desbalance SELL/WAIT/BUY
- Swarm Intelligence mejorado: añadido `swarm_bull_ratio`, corregido lag temporal
- Umbrales recalibrados: `LABEL_THRESHOLD` 0.002→0.007, `MIN_CONFIDENCE` 0.15→0.38
- Modelo v3: entrenado con nuevo pipeline, métricas per-clase visibles
- NOTIONAL_CAP_RATIO: 25%→12%

### v14.9.0 (2026-03-28)
- Sistema de alertas REGULAR + BOUNTY (reemplaza brain_loop individual)
- Score compuesto para ranking de señales
- Timeout automático de señales sin respuesta (5 min)
- Migración BD: columnas `alert_category`, `score` en `pending_approvals`

### v14.8.5 (2026-03-26)
- Fix crítico TP SHORT: `current_price * 0.1` → `current_price * 0.90`
- Fix exposure_warning: rechaza la orden en lugar de solo loguear
- Fix balance portafolio: `binance_reserve` siempre devolvía 0
- Plan B completado: 56/56 tests en verde
- Reentrenamiento con Optuna 50 trials (log-loss 0.2893)
