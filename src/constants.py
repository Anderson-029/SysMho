"""
SysMho — Constantes Globales del Sistema.

Fuente única de verdad para valores compartidos entre módulos.
Cualquier módulo que necesite estos valores debe importarlos
desde aquí en lugar de definirlos localmente.
"""

# ============================================================
# Portafolio Activo de Activos (Fuente Única de Verdad)
# ============================================================
# POL/USDT reemplaza a MATIC/USDT desde la migración v11.0
SYMBOLS = [
    'BTC/USDT',
    'ETH/USDT',
    'BNB/USDT',
    'SOL/USDT',
    'XRP/USDT',
    'ADA/USDT',
    'AVAX/USDT',
    'LINK/USDT',
    'DOT/USDT',
    'POL/USDT',
]

# ============================================================
# Temporalidades
# ============================================================
DEFAULT_TIMEFRAME = '5m'
MACRO_TIMEFRAMES = ['1h', '4h']

# ============================================================
# Entrenamiento de la IA
# ============================================================
MIN_CANDLES_FOR_TRAINING = 1000
MIN_CANDLES_FOR_TUNING = 2000
MIN_CANDLES_FOR_PREDICTION = 20
LABEL_THRESHOLD = 0.007  # 0.7%: movimiento real en futuros 5m (antes 0.2% = ruido)
TRAIN_TEST_SPLIT = 0.15  # 15% para test, 85% para entrenamiento

DEFAULT_MODEL_PARAMS = {
    'n_estimators': 235,       # Óptimo Optuna (antes 150)
    'learning_rate': 0.1259,   # Óptimo Optuna (antes 0.05)
    'max_depth': 5,
    'subsample': 0.8,
    'colsample_bytree': 0.9,
    'eval_metric': 'mlogloss',
    'random_state': 42,
    'n_jobs': -1,              # Todos los hilos disponibles (antes 6)
}

# ============================================================
# Features del Modelo (27 features limpias, sin redundancia)
# Fuente única de verdad para entrenamiento y predicción.
# ============================================================
MODEL_FEATURES = [
    # Momentum 5m
    'rsi_14',           # RSI 14 períodos
    'stoch_rsi_k',      # Stoch RSI K (oscilador de momentum)
    'macd_diff_pct',    # Histograma MACD normalizado (% del precio)

    # Fuerza de tendencia 5m
    'adx',              # Fuerza de la tendencia (ADX)
    'adx_pos',          # Componente alcista del ADX
    'bb_pband',         # Posición en Bollinger (0=banda baja, 1=banda alta)

    # Dinámicas de precio 5m (todo normalizado, sin sesgo de escala)
    'atr_pct',          # Volatilidad como % del precio
    'ema_21_dist',      # Distancia a EMA21 en %
    'ema_200_dist',     # Distancia a EMA200 en % (tendencia macro)
    'vwap_dist',        # Distancia a VWAP en %
    'pct_change',       # Retorno de la vela actual
    'vol_change',       # Cambio en volumen (velocidad del dinero)

    # Contexto de futuros
    'funding_rate',     # Tasa de financiación (sesgo largo/corto del mercado)
    'obi_20',           # Desequilibrio del libro de órdenes

    # Inteligencia de enjambre (estado del portafolio completo)
    'swarm_rsi_avg',    # RSI promedio de los otros 9 activos
    'swarm_macd_avg',   # MACD promedio de los otros 9 activos
    'swarm_bull_ratio', # Fracción de activos en tendencia alcista

    # Contexto macro 1h
    'h1_rsi_14',        # RSI en 1h
    'h1_macd_diff_pct', # Histograma MACD 1h normalizado
    'h1_adx',           # Fuerza de tendencia 1h
    'h1_bb_pband',      # Posición en Bollinger 1h
    'h1_atr_pct',       # Volatilidad 1h como % del precio

    # Contexto macro 4h
    'h4_rsi_14',        # RSI en 4h
    'h4_macd_diff_pct', # Histograma MACD 4h normalizado
    'h4_adx',           # Fuerza de tendencia 4h
    'h4_bb_pband',      # Posición en Bollinger 4h
    'h4_atr_pct',       # Volatilidad 4h como % del precio
]

# ============================================================
# Predictor — Umbrales de Decisión
# (Recalibrados para modelo con clases balanceadas)
# ============================================================
NORMAL_MIN_CONFIDENCE = 0.38   # 38% mínimo (antes 15%, por debajo del azar en 3 clases)
AGGRESSIVE_MIN_CONFIDENCE = 0.05
NORMAL_INERTIA_THRESHOLD = 0.72  # Veto si WAIT > 72% (antes 85%, demasiado restrictivo)
AGGRESSIVE_INERTIA_THRESHOLD = 0.93
NORMAL_STRENGTH_RATIO = 2.0
AGGRESSIVE_STRENGTH_RATIO = 1.0
HIGH_CONVICTION_THRESHOLD = 0.55  # Alta convicción real (antes 0.42, casi azar)

# ============================================================
# Gestión de Riesgos
# ============================================================
BINANCE_FUTURES_TAKER_FEE = 0.0004   # 0.04% por orden de mercado (taker)

NORMAL_RISK_PER_TRADE = 0.02    # 2% del portafolio
AGGRESSIVE_RISK_PER_TRADE = 0.05  # 5% del portafolio
NORMAL_ATR_SL = 1.5
NORMAL_ATR_TP = 3.0
AGGRESSIVE_ATR_SL = 1.0
AGGRESSIVE_ATR_TP = 2.5
MIN_NOTIONAL_USDT = 6.0   # Binance exige 5.0, usamos 6.0
NOTIONAL_CAP_RATIO = 0.12  # Max 12% del capital por trade (antes 25%; 3 alertas = 36% max)
EXPOSURE_LIMIT_RATIO = 0.50  # Alerta si > 50% en posiciones
CAPITAL_SHIELD_RATIO = 0.10  # Escudo SL mínimo 10% del precio
CAPITAL_SHIELD_THRESHOLD = 0.90  # Liquidación preventiva 90%

# ============================================================
# Monitor y Ciclos
# ============================================================
MONITOR_INTERVAL_SECONDS = 1
AUTO_TRAIN_CHECK_SECONDS = 3600       # 1 hora
ACCOUNTING_SYNC_SECONDS = 300         # 5 minutos
SIGNAL_SCANNER_SECONDS = 5            # Scanner de huérfanas

# ============================================================
# Sistema de Alertas (2 tipos: REGULAR y BOUNTY)
# ============================================================
# REGULAR: Top 3 señales cada 5 minutos
TOP_N_SIGNALS = 3
SIGNAL_SCAN_INTERVAL_SECONDS = 300    # 5 min (sincroniza con cierre de vela)

# BOUNTY: señal de alta convicción sin horario fijo
BOUNTY_WATCHER_INTERVAL_SECONDS = 30  # Vigilancia cada 30s
BOUNTY_CONFIDENCE_THRESHOLD = 0.55    # Confianza mínima para BOUNTY
BOUNTY_TREND_ALIGNMENT_REQUIRED = 3   # 5m + 1h + 4h deben coincidir
BOUNTY_MIN_RR_RATIO = 3.0             # TP/SL mínimo para BOUNTY

# Timeout de señales sin respuesta del operador
PENDING_SIGNAL_TIMEOUT_SECONDS = 300  # 5 min → auto-DISMISSED

# ============================================================
# Dashboard — Intervalos de Actualización (ms)
# ============================================================
CHART_REFRESH_MS = 3000
BALANCE_REFRESH_MS = 1000
POSITIONS_REFRESH_MS = 1000
HISTORY_REFRESH_MS = 10000
SIGNALS_REFRESH_MS = 1000
TELEMETRY_REFRESH_MS = 2000
API_STATUS_REFRESH_MS = 15000

# ============================================================
# Versión del Sistema
# ============================================================
SYSMHO_VERSION = '15.2.0'
