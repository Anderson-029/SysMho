# Historial de Cambios

Todos los cambios notables de SysMho se documentan aquí.

Formato: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
Versionado: [Semantic Versioning](https://semver.org/spec/v2.0.0.html)

---

## [Sin Liberar]

### Agregado
- Skill `sysmho-docs`: genera 16 archivos de documentación profesional (ADRs, How-to, Referencia API, Arquitectura C4, Changelog, Configuración, SPEC-001)

---

## [15.2.0] - 2026-04-20

### Agregado
- Gap Filler automático: rellena 11 días de datos faltantes (34,500 velas) en 43 segundos
- Skill `sysmho-docs` con estándares Diátaxis, ADR, Keep-a-Changelog, OpenAPI 3.0, C4 Model
- `.gitignore`: excluir `src/ai/models/` para no subir modelos binarios al repo

### Cambiado
- Retraining XGBoost con datos frescos (2026-04-09 → 2026-04-20), accuracy promedio 98.1% (rango 96.6-100%)
- AGENTS.md: nueva sección Documentación con entrada `sysmho-docs`

---

## [15.2.0] - 2026-04-04 — *Lanzamiento Anterior*

### Agregado
- Gap Filler automático al arranque (`src/collector/gap_filler.py`) — rellena vacíos de datos entre sesiones
- PnL diario con reset manual desde dashboard (`POST /api/portfolio/reset_pnl`)
- Deployment Docker-first: `uv run db-start-docker`, `uv run db-migrate-docker`
- Script `scripts/sysmho.py` con diagnósticos rápidos del sistema

### Cambiado
- XGBoost v3: 28 features (añadido `symbol_encoded` + contexto macro 1h/4h completo)
- Sliding window retrain: ventana 3 meses configurable vía `TRAINING_WINDOW_MONTHS`
- Dashboard: indicadores de badge para posiciones abiertas

### Corregido
- (Commits anteriores en rama SYSMHO-4)

---

## [15.1.0] - 2026-03-29

### Agregado
- Pipeline end-to-end en Binance Testnet validado
- Integración completa WebSocket → Features → XGBoost → Risk → Execute

### Corregido
- Compatibilidad XGBoost 3.2.0 (cambios disruptivos en API)
- Error en cálculo de `pct_change` en FeatureEngineer

---

## [15.0.0] - 2026-03-29

### Agregado
- **Modo autónomo** con MetaEvaluador (5 filtros estadísticos, umbral dinámico 0.52)
- **Circuit Breaker** automático (5 hard stops configurables en `.env`)
- **SelfLearner**: actualiza `meta_stats.json` post-trade (win rate global, by_hour, calibración)
- Tabla `autonomous_decisions` en BD para auditoría de decisiones autónomas
- Tabla `meta_stats` en BD (espejo de `meta_stats.json`)
- Toggle `AUTONOMOUS_MODE` en runtime vía `runtime_state.json` (sin reinicio)

### Cambiado
- Pipeline ML: 27 features → 28 features (añadido `symbol_encoded`)
- `MetaEvaluator`: umbral base 0.52, dinámico por activo (cap 0.75)
- Dashboard: panel autónomo con stats MetaEvaluador, historial decisiones, toggle CB

---

## [14.x.x] - Antes de 2026-03-29

### Resumen
- Modo manual exclusivo (sin autonomía)
- XGBoost básico sin MetaEvaluador
- Dashboard básico (balance, señales, posiciones)
- Sin soporte Docker
- Ver `git log --oneline 4042703..4ee12c8` para historial completo
