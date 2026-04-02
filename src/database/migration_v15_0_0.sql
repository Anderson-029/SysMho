-- SysMho — Migración v15.0.0
-- FASE 4: Pipeline ML rediseñado (Opción B)
-- Ejecutar UNA SOLA VEZ antes del reentrenamiento v3.
--
-- CAMBIOS:
-- 1. Registra el reentrenamiento como versión v3 (features nuevas)
-- 2. Limpia métricas de rendimiento de versiones anteriores (v2)
--    para que el dashboard refleje solo los datos del nuevo modelo.
-- 3. El archivo del modelo (xgboost_v1.joblib) debe borrarse manualmente
--    antes de reentrenar para forzar inicio desde cero con las 27 features.

-- Marcar versiones anteriores como obsoletas (no borrar, para auditoría)
UPDATE model_performance
    SET model_name = REPLACE(model_name, '_v2', '_v2_deprecated')
    WHERE model_name LIKE '%_v2';

-- Índice adicional para acelerar queries de rendimiento por versión
CREATE INDEX IF NOT EXISTS idx_model_performance_name
    ON model_performance(model_name);
