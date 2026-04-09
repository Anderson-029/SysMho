# AGENTS.md — Skills Index + Module Navigation

**See CLAUDE.md first** for critical rules, entry points, and documentation strategy.

---

## Skills Index

Each skill is located in `.claude/skills/{name}/SKILL.md` with YAML frontmatter (`name`, `description`, `allowed-tools`).

Load **only** the skill you need. If the task crosses domains, load max 2–3.

### Operational (12)

| Skill | Description | Path |
|-------|-------------|------|
| `sysmho` | Master diagnostic panel — runs a full system health check in one command. Use when you need a quick overview of all SysMho subsystems. | `.claude/skills/sysmho/SKILL.md` |
| `sysmho-audit` | Full integrity audit — verifies coherence between local DB, Binance and system state. Use when suspecting data mismatches or desynchronization. | `.claude/skills/sysmho-audit/SKILL.md` |
| `sysmho-cb-tune` | Analyzes trade history and suggests optimal Circuit Breaker thresholds with statistical evidence. Use when calibrating CB parameters. | `.claude/skills/sysmho-cb-tune/SKILL.md` |
| `sysmho-deploy` | Controlled restart — verifies open positions, stops processes, applies pending migrations, starts in order. Use when restarting SysMho safely. | `.claude/skills/sysmho-deploy/SKILL.md` |
| `sysmho-logs` | Reads and analyzes neural telemetry from the brain log grouped by event type. Use when investigating runtime behavior or errors. | `.claude/skills/sysmho-logs/SKILL.md` |
| `sysmho-market` | Real-time crypto market context — BTC/ETH trends, funding rates, RSI for all 10 assets and overheating alerts. Use when assessing current market conditions. | `.claude/skills/sysmho-market/SKILL.md` |
| `sysmho-metrics` | Muestra el pipeline completo de predicción, las 28 features del modelo, umbrales dinámicos del MetaEvaluador por activo y estado actual del CircuitBreaker. Usar para entender qué métricas usa SysMho para decidir si operar. | `.claude/skills/sysmho-metrics/SKILL.md` |
| `sysmho-migrate` | Applies SQL migrations safely and verifies they were applied correctly. Use when there are pending database migrations. | `.claude/skills/sysmho-migrate/SKILL.md` |
| `sysmho-performance` | Real performance analysis — KPIs, win rate, PnL, best assets and MetaEvaluator calibration. Use when evaluating trading performance. | `.claude/skills/sysmho-performance/SKILL.md` |
| `sysmho-retrain` | Orchestrates safe XGBoost retraining — verifies data, backs up old model, retrains and validates metrics. Use when the model needs retraining. | `.claude/skills/sysmho-retrain/SKILL.md` |
| `sysmho-signals` | Tactical signals view — pending signals, recent history, approval rate and decision context. Use when reviewing trading signal activity. | `.claude/skills/sysmho-signals/SKILL.md` |
| `sysmho-test` | Runs the complete test suite and reports results with failure context. Use when validating code changes or checking test health. | `.claude/skills/sysmho-test/SKILL.md` |

### Development (6)

| Skill | Description | Path |
|-------|-------------|------|
| `sysmho-cleanup` | Cleans the codebase by removing dead code, unused imports, unconsumed indicators, orphan files — always with evidence and confirmation. Use when reducing technical debt. | `.claude/skills/sysmho-cleanup/SKILL.md` |
| `sysmho-fix` | Bug diagnosis — reads involved files, identifies root cause and proposes exact fix before touching anything. Use when investigating a bug. | `.claude/skills/sysmho-fix/SKILL.md` |
| `sysmho-impact` | Impact analysis before modifying a file or area — transitive dependencies, DB tables, env vars, test coverage and regression risk. Use before modifying any source code. | `.claude/skills/sysmho-impact/SKILL.md` |
| `sysmho-pre-commit` | Pre-save consistency checklist — versions, SQL injection risks, stale constants, dead imports. Use before committing changes. | `.claude/skills/sysmho-pre-commit/SKILL.md` |
| `sysmho-refactor` | Analyzes a module and lists concrete cleanup opportunities with code evidence — no changes without approval. Use when looking for refactoring targets. | `.claude/skills/sysmho-refactor/SKILL.md` |
| `sysmho-test-coverage` | Maps which modules have tests and which critical functions are not covered. Use when deciding which tests to write next. | `.claude/skills/sysmho-test-coverage/SKILL.md` |

### Analytics (2) — *PLANNED PHASE 2*

| Skill | Description | Path | Status |
|-------|-------------|------|--------|
| `sysmho-backtest` | Simulate historical signals — if the model had traded the last 30 days, what would the PnL be? Useful for validation before production. | `.claude/skills/sysmho-backtest/SKILL.md` | 🔵 Planned |
| `sysmho-feature-importance` | Rank the 27 features by importance in predictions. Identify low-impact features for potential cleanup. | `.claude/skills/sysmho-feature-importance/SKILL.md` | 🔵 Planned |

### Reporting (2) — *PLANNED PHASE 3*

| Skill | Description | Path | Status |
|-------|-------------|------|--------|
| `sysmho-risk-report` | Complete risk dashboard — drawdown analysis, exposure limits, Circuit Breaker state, maximum loss scenario. | `.claude/skills/sysmho-risk-report/SKILL.md` | 🔵 Planned |
| `sysmho-weekly` | Weekly summary — PnL trend, win rate by day, best/worst assets, signals rejected vs approved, key insights. | `.claude/skills/sysmho-weekly/SKILL.md` | 🔵 Planned |

---

## Module Navigation

For domain-specific context, read these files on-demand:

| File | Covers |
|------|--------|
| `src/AGENTS.md` | Module architecture, entry points, code conventions, dependency flow |
| `src/ai/AGENTS.md` | ML pipeline, model files, training, MetaEvaluator, SelfLearner |
| `src/database/AGENTS.md` | DB schema, frequent queries, migrations, connection setup |
| `src/dashboard/AGENTS.md` | API routers, authentication, frontend, badge indicators |

---

## Maintenance

### Add / Remove / Modify a Skill

1. Create / edit `.claude/skills/{name}/SKILL.md` with YAML frontmatter
2. Update the appropriate table (Operational or Development) above
3. Commit both changes together

### Update Module Documentation

- If you change module architecture: update `src/AGENTS.md` module map
- If you change DB schema: update `src/database/AGENTS.md`
- If you change ML pipeline: update `src/ai/AGENTS.md`
- If you change API routes: update `src/dashboard/AGENTS.md`

See CLAUDE.md for full maintenance protocol.
