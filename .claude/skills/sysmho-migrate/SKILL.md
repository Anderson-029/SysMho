---
name: sysmho-migrate
description: Applies SQL migrations safely and verifies they were applied correctly. Use when there are pending database migrations.
allowed-tools: Read Shell Glob
---

Orchestrate safe SQL migration application for SysMho.

## Step 1 — Detect pending migrations

List all migration files in `src/database/` — look for `migration_v*.sql` files.

Read each migration file to understand what tables/columns it creates or modifies. Compare against what is known to already be applied (ask the user if unsure about current DB state).

## Step 2 — Verify current DB state

Query the database (connection: `config/settings.py` → `DATABASE_URL`):

```sql
-- List all existing tables
SELECT tablename
FROM pg_catalog.pg_tables
WHERE schemaname = 'public'
ORDER BY tablename;
```

Compare with the tables defined in `src/database/schema.sql` to understand what is already applied.

## Step 3 — Apply the indicated migration

If the user specified a file, apply it using:

```bash
psql $DATABASE_URL -f src/database/migration_vX_Y_Z.sql
```

Or use the psql client configured with the credentials from `config/settings.py` → `DATABASE_URL`.

If the user did not specify a file, list the available migrations and ask which one to apply before proceeding.

## Step 4 — Verify it was applied correctly

After applying, check that each table/column the migration should have created now exists:

```sql
-- Check table existence
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'table_name_here'
ORDER BY ordinal_position;
```

Confirm: ✅ table exists with correct columns / ❌ something failed.

## Step 5 — Verify code coherence

Read the Python files that use the new tables/columns (check `src/database/repository.py` and the relevant dashboard routes). Confirm that field names in the code match exactly what the DDL created. Alert on any discrepancies.

## Result

Report:
- Migration applied: filename
- Tables created/modified with their columns
- Code ↔ DB coherence: ✅ or ❌ with detail
