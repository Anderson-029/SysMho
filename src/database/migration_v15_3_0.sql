-- ============================================================
-- SysMho Migration v15.3.0 — Gemini Intelligence Layer
-- Tabla: gemini_market_context
-- ============================================================

CREATE TABLE IF NOT EXISTS gemini_market_context (
    id                  SERIAL PRIMARY KEY,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),

    -- Scores estructurados para MetaEvaluador
    sentiment_score     NUMERIC(4,3),       -- -1.000 a +1.000
    whale_pressure      SMALLINT,           -- -1 | 0 | 1
    macro_bias          SMALLINT,           -- -1 | 0 | 1
    news_risk_level     SMALLINT,           -- 0 (bajo) | 1 (medio) | 2 (alto)
    optimal_hour        BOOLEAN,            -- ¿Hora actual es buena para operar?
    llm_veto            BOOLEAN DEFAULT FALSE,

    -- Cambios detectados (para lógica de re-investigación)
    significant_changes JSONB,              -- {"news": true, "whales": false, ...}
    sources_checked     TEXT[],             -- Fuentes que Gemini consultó

    -- Reporte completo y razonamiento
    full_report         JSONB NOT NULL,
    gemini_reasoning    TEXT,

    -- Control: fue investigación nueva o reuso del anterior
    was_reinvestigated  BOOLEAN DEFAULT TRUE,
    reuse_count         INTEGER DEFAULT 0,

    version             INTEGER DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_gmc_created
    ON gemini_market_context(created_at DESC);
