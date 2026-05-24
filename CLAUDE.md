# CLAUDE.md — SysMho v15.3.0

**SysMho v15.3.0** — Neural Combat Financial System with Gemini Intelligence.  
Autonomous crypto trading bot on Binance Futures with AI (XGBoost v3 + Gemini Web Intelligence, 28 features).  
Stack: Python 3.12 + FastAPI + PostgreSQL + XGBoost + Gemini API + CCXT Pro.

---

## Critical Rules

- **Paths**: Always relative to workspace root. Never hardcode absolute paths.
- **Database**: Connect via `config/settings.py` → `DATABASE_URL` (loaded from `.env`). Never hardcode credentials.
- **Python execution**: Use `uv run python ...` or `uv run {command}` — manages venv automatically.
- **Constants**: Single source of truth is `src/constants.py` — do not hardcode thresholds elsewhere.
- **Secrets**: All secrets live in `.env` (never committed). Reference via `config/settings.py`.
- **IPC**: `src/runtime_state.json` and `sysmho_brain.log` bridge AI Engine and Dashboard. Paths resolved via `src/paths.py`.
- **Skills**: Load only what the task needs (max 2–3). See skills index in `AGENTS.md`.

---

## Two Processes

| Process | Entry Point | Command | Purpose |
|---------|------------|---------|---------|
| AI Engine | `src/main.py` | `uv run engine` | Trading logic + predictions + learning |
| Dashboard | `src/dashboard/api.py` | `uv run dashboard` | REST API + frontend (port 8000) |

**Database**: PostgreSQL (native or Docker). Apply schema and migrations via `uv run db-migrate`.

---

## Entry Points (Full List)

**Application**:
- `uv run engine` — Start AI Engine
- `uv run dashboard` — Start Dashboard (http://localhost:8000)
- `uv run test` — Run test suite (50+ tests)

**Database** (native PostgreSQL):
- `uv run db-start` — Verify PostgreSQL is reachable
- `uv run db-migrate` — Apply schema + migrations
- `uv run db-seed` — Load seed data (optional)
- `uv run db-backup` — Full backup

**Database** (Docker PostgreSQL):
- `uv run db-start-docker` / `uv run db-stop-docker`
- `uv run db-migrate-docker` / `uv run db-seed-docker`

---

## For Deeper Context — Read Specific AGENTS.md Files

These files contain domain-specific architecture and should be read on-demand:

| File | Covers |
|------|--------|
| `AGENTS.md` (raíz) | Skills index + module navigation |
| `src/AGENTS.md` | Module architecture, entry points, code conventions, dependency flow |
| `src/intelligence/AGENTS.md` | Gemini Intelligence Layer, web investigation, context reporting |
| `src/ai/AGENTS.md` | ML pipeline, model files, training, MetaEvaluator (6 components), SelfLearner |
| `src/database/AGENTS.md` | DB schema, frequent queries, migrations, `gemini_market_context` table |
| `src/dashboard/AGENTS.md` | API routers, authentication, frontend, badge indicators |

**Why separate?** Avoid loading all docs at once. Jump to what you need. Reduces token cost per conversation.

---

## Key Files (Always Relevant)

| File | Role |
|------|------|
| `src/constants.py` | All numeric parameters, thresholds, feature list, symbol portfolio, Gemini constants |
| `src/paths.py` | Centralized data paths (models, logs, IPC files) |
| `src/runtime_config.py` | IPC read/write (autonomous mode, CB reset, PnL reset) |
| `src/intelligence/gemini_agent.py` | GeminiIntelligenceAgent — web investigation, context generation |
| `.env` | Binance keys, DB credentials, CB/Meta thresholds, **GEMINI_API_KEY**, toggles (never committed) |
| `.env.example` | Template for new variables (including GEMINI_API_KEY, GEMINI_MIN_REINVESTIGATE_INTERVAL) |

---

## Maintenance Protocol

### When adding / removing / modifying a skill

1. Create or edit `.claude/skills/{name}/SKILL.md` with YAML frontmatter:
   ```yaml
   ---
   name: skill-name
   description: One-line description of what the skill does.
   allowed-tools: [Read, Bash, ...]
   ---
   ```

2. Update the Skills Index table in `AGENTS.md` (raíz) to match the frontmatter `description` exactly.

3. Commit both changes together (skill + index update).

### When adding / removing a DB table or migration

1. Update `src/database/AGENTS.md` with the new table/migration.
2. Add migration file: `src/database/migration_vX_Y_Z.sql`.
3. Update version in `constants.py` if it's a major change.

### When changing module architecture

1. Update the relevant nested AGENTS.md (e.g., `src/ai/AGENTS.md` if you refactor the ML pipeline).
2. Update `src/AGENTS.md` module map if you add/remove directories.
3. Update `src/AGENTS.md` dependency flow diagram if imports change.

---

## Memory & Documentation Strategy

**Do NOT save in memory** anything already documented here or in AGENTS.md files. Memory is for:
- User preferences (how you like to work)
- Decisions made in prior conversations (e.g., "consolidate docs to 1 CLAUDE.md")
- External links and references
- Project state snapshots (deadlines, blocking issues)

**Prefer reading docs on-demand** over memory.

---

## Version History (Abbreviated)

| Version | Date | Notes |
|---------|------|-------|
| v15.3.0 | 2026-05-23 | Gemini Intelligence Layer, web context investigation, 6-component MetaEvaluador, 28 features |
| v15.2.0 | 2026-04-04 | Gap Filler, PnL diario, Docker-first, 87.5% accuracy |
| v15.0.0 | 2026-03-XX | Autonomous mode, MetaEvaluator, Circuit Breaker, SelfLearner |
| v14.x.x | Before | Manual-only mode, no autonomy |

See `README.md` for full version history and setup instructions.

---

## Quick Diagnostics

```bash
# Full system health check
uv run sysmho

# View live telemetry
uv run sysmho-logs

# Check real-time market context
uv run sysmho-market

# View trading signals (pending, history, approval rate)
uv run sysmho-signals

# View trading performance (KPIs, win rate, best assets)
uv run sysmho-performance
```

(Use skills above as shortcuts — they encapsulate complex queries and business logic.)

---

**Last updated**: 2026-05-23  
**Maintained by**: Anderson  
**Next tasks**: Validate Gemini Intelligence production readiness, accumulate 200+ autonomous trades with Gemini context for Phase 2 meta-model training.
