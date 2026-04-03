---
name: sysmho-impact
description: Impact analysis before modifying a file or area — transitive dependencies, DB tables, env vars, test coverage and regression risk. Use before modifying any source code.
allowed-tools: Read Grep Glob
---

The user indicates a specific file or an area/feature (e.g. "circuit breaker", "positions", "portfolio").
If not indicated, ask what they want to analyze before modifying.

## Step 1 — Identify the scope

**If a file was given**: Read it completely. Identify its purpose, public classes/functions, and mutable state.

**If an area was given**: Search for all Python files in `src/` that mention the term. Read each to understand its role. The rest of the steps apply to every file in the area.

## Step 2 — Dependency tree (2 levels)

**Level 1 — Who imports this file:**
Search for `from ... MODULE import` or `import ... MODULE` patterns in `src/`.

**Level 2 — Who imports those that import this file:**
Repeat the search for each file found in Level 1.

## Step 3 — DB tables and queries

Search for SELECT, INSERT, UPDATE, DELETE, FROM, JOIN patterns in the file(s).

For each table found, check in other modules whether concurrent write conflicts are possible.

## Step 4 — Environment variables

Search for `os.getenv` and `os.environ` patterns in the file(s).

Verify those variables are documented in `.env.example`.

## Step 5 — Side effects

Identify:
- Does it write files? (`open`, `write`, `os.replace`, `json.dump`)
- Does it write to DB? (INSERT, UPDATE, DELETE)
- Does it call Binance? (`exchange`, `ccxt`, `fetch_`)
- Does it modify `src/runtime_state.json`? (`_save`, `set_autonomous`, `set_sync_status`)
- Is it in a critical loop of `main.py`? (asyncio task)

## Step 6 — Test coverage

Search for the module/area name in `tests/` to find covering tests. For each test found, read the first 30 lines to understand what is tested. Identify which functions have tests and which do not.

## Step 7 — Impact report

```
SCOPE: [file path or area name]
Purpose: ...
─────────────────────────────────────────────────────────
FILES IN SCOPE:
  src/executor/circuit_breaker.py — CircuitBreaker
  src/main.py — uses CircuitBreaker in _autonomous_decide()

DIRECT DEPENDENTS (level 1):
  src/main.py, src/dashboard/routes/autonomous.py

INDIRECT DEPENDENTS (level 2):
  none additional

DB TABLES:     [table (R/W)] or none
ENV VARS:      [list] → all in .env ✅/❌
SIDE EFFECTS:  [list] or none
CRITICAL LOOP: yes/no

TESTS:         tests/test_phase5.py — basic coverage
               ⚠️ No test for: [uncovered functions]

CHANGE RISK: HIGH / MEDIUM / LOW
FILES TO UPDATE IF YOU CHANGE THE INTERFACE:
  [file:line — call site description]
```
