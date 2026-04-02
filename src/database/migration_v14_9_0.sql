-- SysMho — Migración v14.9.0
-- Añade soporte para el nuevo sistema de alertas (REGULAR y BOUNTY)
-- Ejecutar UNA SOLA VEZ sobre la BD existente.

ALTER TABLE pending_approvals
    ADD COLUMN IF NOT EXISTS alert_category VARCHAR(10) DEFAULT 'REGULAR',
    ADD COLUMN IF NOT EXISTS score DECIMAL(8,6) DEFAULT 0.0;

CREATE INDEX IF NOT EXISTS idx_pending_status
    ON pending_approvals(status);

CREATE INDEX IF NOT EXISTS idx_pending_category
    ON pending_approvals(alert_category);

CREATE INDEX IF NOT EXISTS idx_market_data_symbol_tf
    ON market_data(symbol, timeframe, open_time DESC);
