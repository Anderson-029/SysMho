-- Datos de mercado históricos
CREATE TABLE IF NOT EXISTS market_data (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    open_time TIMESTAMPTZ NOT NULL,
    open DECIMAL(18,8) NOT NULL,
    high DECIMAL(18,8) NOT NULL,
    low DECIMAL(18,8) NOT NULL,
    close DECIMAL(18,8) NOT NULL,
    volume DECIMAL(18,8) NOT NULL,
    atr_14 DECIMAL(18,8),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(symbol, timeframe, open_time)
);

-- Sensor Institucional (Funding Rate + Open Interest + Liquidity)
CREATE TABLE IF NOT EXISTS sentiment_data (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL UNIQUE,
    funding_rate DECIMAL(18,8),
    open_interest DECIMAL(18,8),
    obi_20 DECIMAL(5,4) DEFAULT 0.0,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Operaciones realizadas por el bot
CREATE TABLE IF NOT EXISTS trades (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(4) NOT NULL,          -- BUY / SELL
    order_type VARCHAR(10) NOT NULL,   -- MARKET / LIMIT
    quantity DECIMAL(18,8) NOT NULL,
    price DECIMAL(18,8) NOT NULL,
    total DECIMAL(18,8) NOT NULL,
    fee DECIMAL(18,8) DEFAULT 0,
    pnl DECIMAL(18,8),                 -- Ganancia/pérdida
    signal_source VARCHAR(50),         -- Origen de la señal (ej: XGBoost_v1_IA)
    leverage DECIMAL(5,2) DEFAULT 1.0,
    invested_usdt DECIMAL(18,8) DEFAULT 0,
    order_id VARCHAR(50),
    status VARCHAR(20) DEFAULT 'EXECUTED',
    executed_at TIMESTAMPTZ DEFAULT NOW()
);

-- Posiciones abiertas
CREATE TABLE IF NOT EXISTS positions (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL UNIQUE,
    side VARCHAR(4) NOT NULL,
    entry_price DECIMAL(18,8) NOT NULL,
    quantity DECIMAL(18,8) NOT NULL,
    current_price DECIMAL(18,8),
    stop_loss DECIMAL(18,8),
    take_profit DECIMAL(18,8),
    pnl_unrealized DECIMAL(18,8),
    invested_usdt DECIMAL(18,8) DEFAULT 0,
    leverage DECIMAL(5,2) DEFAULT 1.0,
    opened_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Rendimiento de modelos de IA
CREATE TABLE IF NOT EXISTS model_performance (
    id BIGSERIAL PRIMARY KEY,
    model_name VARCHAR(100) NOT NULL,
    accuracy DECIMAL(5,4),
    precision_score DECIMAL(5,4),
    recall DECIMAL(5,4),
    total_predictions INT DEFAULT 0,
    correct_predictions INT DEFAULT 0,
    trained_at TIMESTAMPTZ DEFAULT NOW()
);

-- Log de decisiones de riesgo
CREATE TABLE IF NOT EXISTS risk_log (
    id BIGSERIAL PRIMARY KEY,
    signal_type VARCHAR(20) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    reason VARCHAR(255),
    approved BOOLEAN NOT NULL,
    risk_score DECIMAL(5,4),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Balance del portafolio
CREATE TABLE IF NOT EXISTS portfolio (
    id BIGSERIAL PRIMARY KEY,
    total_balance DECIMAL(18,8) NOT NULL,
    available_balance DECIMAL(18,8) NOT NULL,
    in_positions DECIMAL(18,8) DEFAULT 0,
    total_pnl DECIMAL(18,8) DEFAULT 0,
    win_rate DECIMAL(5,4) DEFAULT 0,
    recorded_at TIMESTAMPTZ DEFAULT NOW()
);

-- Alertas pendientes de aprobación humana con proyecciones financieras
CREATE TABLE IF NOT EXISTS pending_approvals (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(4) NOT NULL,
    quantity DECIMAL(18,8) NOT NULL,
    entry_price DECIMAL(18,8) NOT NULL,
    stop_loss DECIMAL(18,8) NOT NULL,
    take_profit DECIMAL(18,8) NOT NULL,
    risk_score DECIMAL(5,4),
    invested_usdt DECIMAL(18,8),         -- Monto total en USDT a invertir
    win_probability DECIMAL(5,4),        -- Probabilidad de éxito según IA
    loss_probability DECIMAL(5,4),       -- Probabilidad de fracaso según IA
    potential_profit_usdt DECIMAL(18,8), -- Ganancia estimada si toca TP
    potential_loss_usdt DECIMAL(18,8),   -- Pérdida estimada si toca SL
    exposure_warning BOOLEAN DEFAULT FALSE,
    signal_type VARCHAR(20),
    trend_5m VARCHAR(10),
    trend_1h VARCHAR(10),
    trend_4h VARCHAR(10),
    alert_category VARCHAR(10) DEFAULT 'REGULAR', -- 'REGULAR' | 'BOUNTY'
    score DECIMAL(8,6) DEFAULT 0.0,               -- Score compuesto para ranking
    status VARCHAR(20) DEFAULT 'PENDING',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
);

-- Índices para queries frecuentes
CREATE INDEX IF NOT EXISTS idx_pending_status ON pending_approvals(status);
CREATE INDEX IF NOT EXISTS idx_pending_category ON pending_approvals(alert_category);
CREATE INDEX IF NOT EXISTS idx_market_data_symbol_tf ON market_data(symbol, timeframe, open_time DESC);
