---
name: database
description: "Database operations: migration (create Alembic migrations, sync init scripts, update data dict) and reset (drop/recreate database). Actions: migrate, reset, sync. Triggers: after model changes, when user asks to reset database. Files: backend/app/models/*.py, backend/alembic/versions/*.py, backend/database/init/*.sql, docs/data-dict/*.md"
---

# Database

Run database migration, reset, and sync workflows.

## Required Sources

- `deployment/.env`
- `deployment/dev/compose.yaml`
- `deployment/compose.base.yaml`
- `deployment/*/compose.yaml`
- `backend/database/init/`
- `backend/alembic/`

## Operations

- Migration workflow: [migration.md](./migration.md)
- Reset workflow: [reset.md](./reset.md)

## Rules

1. Migration-first: never patch runtime DB manually as replacement for migration.
2. Maintain three-way sync:
   - `backend/app/models/*.py`
   - `backend/database/init/*.sql`
   - `docs/data-dict/*.md`
3. Reset requires explicit user confirmation.
4. Never run reset on production-like environments.
5. Block completion if sync or migration verification fails.
