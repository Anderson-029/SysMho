# AGENTS.md — SysMho

## Identity

**SysMho v15.2.0 — Neural Combat Financial System.**
Autonomous crypto trading bot on Binance Futures with AI (XGBoost v3, 27 features).
Stack: Python 3.12 + FastAPI + PostgreSQL + XGBoost + CCXT Pro.

---

## Critical Rules

- **Paths**: Always relative to workspace root. Never hardcode absolute paths.
- **Database**: Connect via `config/settings.py` → `DATABASE_URL` (loaded from `.env`). Never hardcode host, user, or password.
- **Python execution**: Use `uv run python ...` — manages venv automatically, cross-platform.
- **Skills**: Do NOT load all skills at once. Check the index below, load only what the task needs (max 2–3).
- **Constants**: Single source of truth is `src/constants.py` — do not hardcode thresholds elsewhere.
- **Secrets**: All secrets live in `.env` (never committed). Reference them via `config/settings.py`. Never modify env files directly; document new variables in `.env.example`.
- **IPC**: `src/runtime_state.json` and `sysmho_brain.log` bridge the AI Engine and Dashboard. Paths resolved via `src/paths.py`.
- **Paths**: IPC/model/log paths are centralized in `src/paths.py`. Never use `__file__`-relative paths for data files.
- **Deep context**: `README.md` (setup, config, version history). For live audits, use the `sysmho-audit` or `sysmho-performance` skills.

---

## Two Processes

| Process | Entry Point | Command | Env file |
|---------|------------|---------|----------|
| AI Engine | `src/main.py` | `uv run engine` | `.env` |
| Dashboard | `src/dashboard/api.py` | `uv run dashboard` | `.env` |

Database: PostgreSQL (native or Docker container — user's choice). Schema and migrations are applied via CLI entry points (idempotent, cross-platform).

```bash
uv run db-start-docker    # start PostgreSQL container
uv run db-migrate         # apply schema + migrations
uv run engine             # start AI engine
uv run dashboard          # start dashboard API
uv run test               # run test suite
```

Communication: PostgreSQL (shared data) + `src/runtime_state.json` (IPC: autonomous mode, CB reset, PnL reset, sync status) + `sysmho_brain.log` (live telemetry). Paths resolved via `src/paths.py`.

**Env file** (never committed): `.env` — Binance keys, `DB_*`, CB/Meta thresholds, `AUTONOMOUS_MODE`, `DASHBOARD_API_KEY`, etc. Template: `.env.example`.

---

## Skills Index

> **Index rule**: Each row mirrors the `name` and `description` from the corresponding `.claude/skills/{name}/SKILL.md` frontmatter. When adding, removing, or modifying any skill, update this index to match. To rebuild from scratch: scan all `.claude/skills/*/SKILL.md`, extract each YAML frontmatter `name` and `description`, and regenerate the tables below.

Load **only** the skill you need. If the task crosses domains, load max 2–3.

### Operational (11)

| Skill | Description | Path |
|-------|-------------|------|
| `sysmho` | Master diagnostic panel — runs a full system health check in one command. Use when you need a quick overview of all SysMho subsystems. | `.claude/skills/sysmho/SKILL.md` |
| `sysmho-deploy` | Controlled restart — verifies open positions, stops processes, applies pending migrations, starts in order. Use when restarting SysMho safely. | `.claude/skills/sysmho-deploy/SKILL.md` |
| `sysmho-signals` | Tactical signals view — pending signals, recent history, approval rate and decision context. Use when reviewing trading signal activity. | `.claude/skills/sysmho-signals/SKILL.md` |
| `sysmho-logs` | Reads and analyzes neural telemetry from the brain log grouped by event type. Use when investigating runtime behavior or errors. | `.claude/skills/sysmho-logs/SKILL.md` |
| `sysmho-performance` | Real performance analysis — KPIs, win rate, PnL, best assets and MetaEvaluator calibration. Use when evaluating trading performance. | `.claude/skills/sysmho-performance/SKILL.md` |
| `sysmho-market` | Real-time crypto market context — BTC/ETH trends, funding rates, RSI for all 10 assets and overheating alerts. Use when assessing current market conditions. | `.claude/skills/sysmho-market/SKILL.md` |
| `sysmho-test` | Runs the complete test suite and reports results with failure context. Use when validating code changes or checking test health. | `.claude/skills/sysmho-test/SKILL.md` |
| `sysmho-audit` | Full integrity audit — verifies coherence between local DB, Binance and system state. Use when suspecting data mismatches or desynchronization. | `.claude/skills/sysmho-audit/SKILL.md` |
| `sysmho-migrate` | Applies SQL migrations safely and verifies they were applied correctly. Use when there are pending database migrations. | `.claude/skills/sysmho-migrate/SKILL.md` |
| `sysmho-retrain` | Orchestrates safe XGBoost retraining — verifies data, backs up old model, retrains and validates metrics. Use when the model needs retraining. | `.claude/skills/sysmho-retrain/SKILL.md` |
| `sysmho-cb-tune` | Analyzes trade history and suggests optimal Circuit Breaker thresholds with statistical evidence. Use when calibrating CB parameters. | `.claude/skills/sysmho-cb-tune/SKILL.md` |
| `sysmho-model-eval` | Evaluates and compares current XGBoost model against previous backups — prediction metrics, confidence distribution, real win rate, and MEJORANDO/EMPEORANDO/ESTABLE verdict with evidence. Use when assessing model performance evolution. | `.claude/skills/sysmho-model-eval/skill_relacion_predicciones.md` |

### Development (6)

| Skill | Description | Path |
|-------|-------------|------|
| `sysmho-impact` | Impact analysis before modifying a file or area — transitive dependencies, DB tables, env vars, test coverage and regression risk. Use before modifying any source code. | `.claude/skills/sysmho-impact/SKILL.md` |
| `sysmho-fix` | Bug diagnosis — reads involved files, identifies root cause and proposes exact fix before touching anything. Use when investigating a bug. | `.claude/skills/sysmho-fix/SKILL.md` |
| `sysmho-refactor` | Analyzes a module and lists concrete cleanup opportunities with code evidence — no changes without approval. Use when looking for refactoring targets. | `.claude/skills/sysmho-refactor/SKILL.md` |
| `sysmho-test-coverage` | Maps which modules have tests and which critical functions are not covered. Use when deciding which tests to write next. | `.claude/skills/sysmho-test-coverage/SKILL.md` |
| `sysmho-pre-commit` | Pre-save consistency checklist — versions, SQL injection risks, stale constants, dead imports. Use before committing changes. | `.claude/skills/sysmho-pre-commit/SKILL.md` |
| `sysmho-cleanup` | Cleans the codebase by removing dead code, unused imports, unconsumed indicators, orphan files — always with evidence and confirmation. Use when reducing technical debt. | `.claude/skills/sysmho-cleanup/SKILL.md` |



---

## Module Context

For area-specific context, read the relevant nested file:

| File | Covers |
|------|--------|
| `src/AGENTS.md` | Module architecture, entry points, code conventions |
| `src/database/AGENTS.md` | DB schema, frequent queries, migration conventions |
| `src/ai/AGENTS.md` | ML pipeline, model files, training commands, MetaEvaluator |
| `src/dashboard/AGENTS.md` | API routers, authentication, frontend, badge indicators |

---

## Maintenance Protocol

Keep the agentic setup in sync with the codebase. Apply after any structural change:

### Skills (`.claude/skills/`)

- **Added a skill**: Create `.claude/skills/{name}/SKILL.md` with YAML frontmatter (`name`, `description`, and optionally `allowed-tools`, `compatibility`, `metadata`). Add a row to the Skills Index above matching the frontmatter `description` exactly.
- **Removed a skill**: Delete the folder under `.claude/skills/`. Remove its row from the Skills Index.
- **Modified a skill's description**: Update the corresponding row in the Skills Index to match the new frontmatter `description`.
- **Rebuild index from scratch**: Scan all `.claude/skills/*/SKILL.md`, read each YAML frontmatter, regenerate both tables grouped by Operational and Development.

### Source code (reflects in nested AGENTS.md)

- **Added/removed a module in `src/`**: Update `src/AGENTS.md` module map.
- **Added/removed a DB table or migration**: Update `src/database/AGENTS.md`.
- **Added/removed an API route or router**: Update `src/dashboard/AGENTS.md`.
- **Changed model features or training pipeline**: Update `src/ai/AGENTS.md`.
- **Changed entry points or CLI commands**: Update the Two Processes table above and `README.md` command tables.

### What NOT to update inline

- `README.md` — human-facing; update only for setup/install/config changes.
