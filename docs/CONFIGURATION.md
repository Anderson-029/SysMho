# Referencia de Configuración de SysMho

**Versión:** 15.2.0 | **Última actualización:** 2026-04-20

Toda la configuración se encuentra en dos lugares:
- `.env` — secretos y parámetros ajustables en tiempo de ejecución (nunca committed a git)
- `src/constants.py` — umbrales algorítmicos (requieren cambio de código + reinicio)

---

## Variables de Entorno (.env)

Copia `.env.example` a `.env` y completa tus valores.

### Requeridas

| Variable | Descripción |
|----------|-------------|
| `BINANCE_API_KEY` | Clave API Binance Futures (se requieren permisos de Futures) |
| `BINANCE_SECRET_KEY` | Clave Secreta Binance Futures |

### Base de Datos

| Variable | Default | Descripción |
|----------|---------|-------------|
| `DB_HOST` | `localhost` | Nombre de host PostgreSQL |
| `DB_PORT` | `5432` | Puerto PostgreSQL |
| `DB_USER` | `postgres` | Usuario PostgreSQL |
| `DB_PASSWORD` | `changeme` | Contraseña PostgreSQL |
| `DB_NAME` | `sysmho` | Nombre de base de datos PostgreSQL |

### Modo Binance

| Variable | Default | Descripción |
|----------|---------|-------------|
| `BINANCE_TESTNET` | `True` | `True` = testnet (trading en papel), `False` = mainnet (dinero real) |

> ⚠️ Nunca establezas `BINANCE_TESTNET=False` hasta haber validado el pipeline completo en testnet.

### Comportamiento del Engine

| Variable | Default | Descripción |
|----------|---------|-------------|
| `AUTONOMOUS_MODE` | `false` | `true` = MetaEvaluador decide autónomamente (sin aprobación humana) |
| `LEARNING_LOOP_SECONDS` | `60` | Con qué frecuencia el learning loop verifica nuevas operaciones cerradas |

### Seguridad del Dashboard

| Variable | Default | Descripción |
|----------|---------|-------------|
| `DASHBOARD_API_KEY` | `` (vacío) | Vacío = acceso abierto (desarrollo). Establece una cadena secreta para seguridad en producción. |

### MetaEvaluador

| Variable | Default | Descripción |
|----------|---------|-------------|
| `META_SCORE_THRESHOLD` | `0.52` | Puntuación meta mínima para auto-aprobar una señal [0,1] |
| `META_MIN_TRADES` | `10` | Operaciones mínimas por símbolo para activar filtrado estadístico |
| `META_MIN_FOR_MODEL` | `200` | Operaciones necesarias para entrenar meta-model Phase 2 |

### Circuit Breaker

| Variable | Default | Rango Seguro | Descripción |
|----------|---------|-------------|-------------|
| `CB_MAX_POSITIONS` | `3` | 2-5 | Max posiciones abiertas simultáneamente |
| `CB_MAX_DAILY_TRADES` | `8` | 4-15 | Max operaciones por día |
| `CB_MAX_CONSEC_LOSSES` | `3` | 2-5 | Max pérdidas consecutivas |
| `CB_DAILY_LOSS_PCT` | `0.04` | 0.02-0.08 | Max drawdown diario (4% = conservador) |
| `CB_WEEKLY_DRAWDOWN_PCT` | `0.08` | 0.05-0.15 | Max drawdown semanal (8%) |

> ⚠️ Nunca establezas `CB_DAILY_LOSS_PCT` sobre 0.10 — riesgo de liquidación.

---

## Umbrales del Predictor (src/constants.py)

Estos controlan qué tan agresivo es el filtro de señales. Mayor = menos pero señales de mayor calidad.

| Constante | Valor | Cuándo ajustar |
|----------|-------|----------------|
| `NORMAL_INERTIA_THRESHOLD` | `0.72` | Disminuir si hay demasiadas señales WAIT. Aumentar si hay overtrading. |
| `NORMAL_MIN_CONFIDENCE` | `0.38` | Disminuir para más señales, aumentar para menos/mayor calidad |
| `NORMAL_STRENGTH_RATIO` | `2.0` | Aumentar en mercados ranging, disminuir en tendencias fuertes |
| `HIGH_CONVICTION_THRESHOLD` | `0.55` | Confianza necesaria para clasificar una señal como PREMIUM/BOUNTY |
| `AGGRESSIVE_MIN_CONFIDENCE` | `0.05` | Threshold para modo AGGRESSIVE (usado internamente por lógica bounty) |

---

## Parámetros de Entrenamiento (src/constants.py)

| Constante | Valor | Descripción |
|----------|-------|-------------|
| `TRAINING_WINDOW_MONTHS` | `3` | Sliding window: entrenar con últimos 3 meses de datos |
| `LABEL_THRESHOLD` | `0.007` | Movimiento de precio mínimo (0.7%) para etiquetar vela como BUY/SELL |
| `TRAIN_TEST_SPLIT` | `0.15` | 15% de datos reservados para validación final hold-out |
| `MIN_CANDLES_FOR_TRAINING` | `1000` | Saltar símbolo si tiene menos velas (ej: listado nuevo) |
| `CANDLES_PER_MONTH_5M` | `8640` | Referencia: 30d × 24h × 12 velas/h |

### Hiperparámetros XGBoost Por Defecto

Se aplican cuando `best_params.joblib` no existe (antes del primer tuning Optuna):

| Parámetro | Valor |
|----------|-------|
| `n_estimators` | 235 |
| `learning_rate` | 0.1259 |
| `max_depth` | 5 |
| `subsample` | 0.8 |
| `colsample_bytree` | 0.9 |
| `eval_metric` | `mlogloss` |

---

## Parámetros de Gestión de Riesgo (src/constants.py)

| Constante | Valor | Descripción |
|----------|-------|-------------|
| `NORMAL_RISK_PER_TRADE` | `0.02` | 2% del capital por operación NORMAL |
| `AGGRESSIVE_RISK_PER_TRADE` | `0.05` | 5% del capital por operación AGGRESSIVE |
| `NOTIONAL_CAP_RATIO` | `0.12` | Hard cap: ninguna operación > 12% del capital |
| `EXPOSURE_LIMIT_RATIO` | `0.50` | Threshold de alerta: alerta si > 50% capital en posiciones abiertas |
| `NORMAL_ATR_SL` | `1.5` | Multiplicador Stop-loss: `SL = entry_price - ATR × 1.5` |
| `NORMAL_ATR_TP` | `3.0` | Multiplicador Take-profit: `TP = entry_price + ATR × 3.0` (R/R = 2.0) |
| `AGGRESSIVE_ATR_SL` | `1.0` | SL más ajustado para señales agresivas |
| `AGGRESSIVE_ATR_TP` | `2.5` | TP para señales agresivas |
| `MIN_NOTIONAL_USDT` | `6.0` | Tamaño de orden mínimo (mínimo de Binance) |
| `BINANCE_FUTURES_TAKER_FEE` | `0.0004` | 0.04% fee de taker (factorizado en cálculo de P&L) |

---

## Ventanas Temporales (src/constants.py)

| Constante | Valor | Descripción |
|----------|-------|-------------|
| `DESTRUCTIVE_HOUR_START` | `14` | UTC — inicio de ventana de alto riesgo (volatilidad institucional) |
| `DESTRUCTIVE_HOUR_END` | `17` | UTC — fin de ventana de alto riesgo |
| `DESTRUCTIVE_HOUR_PENALTY` | `0.08` | Extra +0.08 agregado al threshold del MetaEvaluador durante esta ventana |

> La ventana destructiva (14-17 UTC) es cuando abren los mercados de EE.UU. y causan alta volatilidad cripto. MetaEvaluador automáticamente aumenta su threshold de aprobación durante este período.

---

## Timing de Señales (src/constants.py)

| Constante | Valor | Descripción |
|----------|-------|-------------|
| `SIGNAL_SCANNER_SECONDS` | `5` | Con qué frecuencia el escáner de señales verifica nuevas oportunidades |
| `BOUNTY_WATCHER_INTERVAL_SECONDS` | `30` | Con qué frecuencia las señales BOUNTY se re-evalúan |
| `PENDING_SIGNAL_TIMEOUT_SECONDS` | `300` | Señal pendiente expira automáticamente en 5 minutos si no se actúa |
| `TOP_N_SIGNALS` | `3` | Max señales insertadas por ciclo de escaneo |
| `MONITOR_INTERVAL_SECONDS` | `1` | Frecuencia de verificación del monitor de posiciones |
| `AUTO_TRAIN_CHECK_SECONDS` | `3600` | Con qué frecuencia el engine verifica si se necesita reentrenamiento |
| `ACCOUNTING_SYNC_SECONDS` | `300` | Con qué frecuencia se sincroniza balance/portafolio a BD |

---

## Portafolio de Símbolos (src/constants.py)

10 activos actuales y sus encodings estables de enteros:

| Símbolo | Encoded como |
|---------|-------------|
| BTC/USDT | 0 |
| ETH/USDT | 1 |
| BNB/USDT | 2 |
| SOL/USDT | 3 |
| XRP/USDT | 4 |
| ADA/USDT | 5 |
| AVAX/USDT | 6 |
| LINK/USDT | 7 |
| DOT/USDT | 8 |
| POL/USDT | 9 |

> ⚠️ Agregar o eliminar símbolos requiere borrar el modelo XGBoost y reentrenar. Ver `docs/how-to/HOW-TO-add-symbol.md`.
