-- ============================================================
-- SysMho Migration v15.2.0 — Sistema de Autonomía
-- Tabla: autonomous_decisions
-- ============================================================

CREATE TABLE IF NOT EXISTS autonomous_decisions (
    id              SERIAL PRIMARY KEY,
    pending_id      INTEGER NOT NULL,
    symbol          VARCHAR(20) NOT NULL,
    decision        VARCHAR(10) NOT NULL,          -- 'APPROVED' | 'REJECTED'
    meta_score      NUMERIC(5, 4),                 -- Score compuesto [0..1]
    confidence      NUMERIC(5, 4),
    direction       VARCHAR(5),                    -- 'LONG' | 'SHORT'
    reasons         TEXT[],                        -- Array de razones
    cb_active       BOOLEAN DEFAULT FALSE,         -- ¿Disparó el circuit breaker?
    cb_reason       TEXT,                          -- Motivo del circuit breaker
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_adec_symbol ON autonomous_decisions(symbol);
CREATE INDEX IF NOT EXISTS idx_adec_created ON autonomous_decisions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_adec_decision ON autonomous_decisions(decision);

-- ============================================================
-- Tabla: meta_stats  (estadísticas por símbolo y hora)
-- Usada por MetaEvaluator para calibración estadística
-- ============================================================

CREATE TABLE IF NOT EXISTS meta_stats (
    id              SERIAL PRIMARY KEY,
    symbol          VARCHAR(20) NOT NULL,
    hour_utc        SMALLINT NOT NULL,             -- 0..23
    direction       VARCHAR(5) NOT NULL,           -- 'LONG' | 'SHORT'
    total_trades    INTEGER DEFAULT 0,
    winning_trades  INTEGER DEFAULT 0,
    win_rate        NUMERIC(5, 4),
    avg_pnl_pct     NUMERIC(8, 4),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (symbol, hour_utc, direction)
);

CREATE INDEX IF NOT EXISTS idx_mstats_symbol ON meta_stats(symbol);
