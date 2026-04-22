---
name: database
description: "Database operations: migration (create Alembic migrations), bootstrap provisioning, and reset. Actions: migrate, reset, sync. Triggers: after model changes, when user asks to reset database. Files: backend/app/models/*.py, backend/alembic/versions/*.py, backend/database/bootstrap/*, backend/database/init/init.sh, scripts/deploy/provision.py"
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
2. Maintain single-source sync:
   - source-of-truth: `backend/alembic/versions/*.py`
   - init infra: `backend/database/init/init.sh` (extensions/privileges only)
   - bootstrap baseline: `backend/database/bootstrap/base.sql` + `backend/database/bootstrap/env/*.sql`
   - dev fixtures: `backend/database/bootstrap/seeds/dev.sql`
   - model files are implementation artifacts and must stay consistent with migrations
3. Reset requires explicit user confirmation.
4. Never run reset on production-like environments.
5. Block completion if sync or migration verification fails.
