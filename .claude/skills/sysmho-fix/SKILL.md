---
name: sysmho-fix
description: Bug diagnosis — reads involved files, identifies root cause and proposes exact fix before touching anything. Use when investigating a bug.
allowed-tools: Read Grep Glob Shell
---

The user describes the bug or incorrect behavior.
If the description is vague, look in the log and DB to reproduce it.

## Step 1 — Collect evidence

**In the neural log** — read `src/sysmho_brain.log` and search for lines containing ERROR, Exception, Traceback, or ❌. Focus on the most recent occurrences.

**In the DB if applicable** — query relevant tables based on the bug description. Use the database connection from `config/settings.py` → `DATABASE_URL`.

Example queries depending on the bug:
- For trade issues: query `trades` and `positions`
- For signal issues: query `pending_approvals` and `autonomous_decisions`
- For portfolio issues: query `portfolio`

## Step 2 — Locate the culprit code

Search for the symptom in the code — use Grep to find the error term or suspicious function name in `src/`.

Read the relevant files completely to understand the exact flow.

## Step 3 — Mentally reproduce the bug

Trace the execution flow step by step:
- Which function starts the chain?
- Where is the incorrect value introduced?
- What condition causes the failure?
- Is it a logic bug, type error, async timing issue, or DB state issue?

## Step 4 — Propose the fix

BEFORE touching anything, present:

```
BUG DIAGNOSED:
─────────────────────────────────────────────────────
Symptom: [what the user reported]
Root cause: [the real problem found]
File: src/FILE.py line N
Current code:
  [exact fragment with the bug]

Proposed fix:
  [corrected code]

Affected files: [list]
Tests to update: [list or "none"]
Regression risk: LOW / MEDIUM / HIGH

Apply the fix? (yes/no)
```

Wait for confirmation before modifying any file.

## Step 5 — Apply and verify

Only if the user confirms:
1. Apply the fix using the Edit tool
2. If there is a relevant test, update it
3. Verify nothing adjacent broke:

```bash
uv run python -c "from src.MODULE import CLASS; print('✅ Import OK')"
```
