---
name: database
description: "Database operations: migration (create Alembic migrations, sync init scripts, update data dict) and reset (drop/recreate database). Actions: migrate, reset, sync. Triggers: after model changes, when user asks to reset database. Files: backend/app/models/*.py, backend/alembic/versions/*.py, backend/database/init/*.sql, docs/data-dict/*.md"
---

# Database

Unified database operations including migrations and resets. Ensures schema changes are properly versioned and documentation stays synchronized.

## When to Use

Run this skill:
- **Migration**: After modifying SQLAlchemy models, adding/removing tables or columns
- **Reset**: When user explicitly asks to "reset database" or needs clean slate
- **Sync**: When database documentation is out of sync

## Quick Start

**Create migration after model changes**:
```bash
# Specify: --migrate or just "migrate"
```

**Reset database to clean state**:
```bash
# Specify: --reset or just "reset"
# Will ask for confirmation before proceeding
```

## Configuration

**Read from actual config files** (never hardcoded):
- Database config: `deployment/.env` (POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD)
- Docker config: `deployment/docker-compose.yml`
- Init scripts: `backend/database/init/`

**Verify configuration before running**:
```bash
cd deployment
grep -E "POSTGRES_DB|POSTGRES_USER" .env
```

## Operations

### Migration

Create and apply database migrations.

**See**: [migration.md](./migration.md) for detailed migration workflow.

**Quick summary**:
1. Verify model changes
2. Create Alembic migration
3. Review generated migration
4. Update init scripts (01_schema.sql)
5. Update data dictionary (docs/data-dict/*.md)
6. Verify three-way sync
7. Test migration

**Three-way sync requirement**:
1. SQLAlchemy Models (`backend/app/models/*.py`)
2. Init Scripts (`backend/database/init/01_schema.sql`)
3. Data Dictionary (`docs/data-dict/*.md`)

All three must be synchronized.

### Reset

Drop and recreate database from init scripts.

**See**: [reset.md](./reset.md) for detailed reset workflow.

**Quick summary**:
1. Confirm with user (REQUIRED)
2. Check environment (not production)
3. Stop backend service
4. Drop and recreate database
5. Run init scripts
6. Verify database state
7. Stamp Alembic version
8. Restart backend

**⚠️ WARNING**: This is DESTRUCTIVE and will DELETE ALL DATA.

## Important Rules

1. **Always create migration first** - Never manually edit database
2. **Three-way sync is mandatory** - Models, init scripts, and docs must match
3. **Test before committing** - Verify migration works and init script is correct
4. **Never reset production** - Always check environment first
5. **Always confirm reset** - Never proceed without explicit user confirmation

## Common Issues

### Migration Issues

**"Target database is not up to date"**
- Cause: Local database behind migration history
- Solution: Run `alembic upgrade head`

**Autogenerate misses changes**
- Cause: Alembic can't detect certain changes (e.g., renames)
- Solution: Manually edit migration file

**Migration fails on existing data**
- Cause: Adding NOT NULL column to table with existing rows
- Solution: Two-step migration (add as nullable first, then make NOT NULL)

**Init script out of sync**
- Cause: Forgot to update init script after migration
- Solution: Regenerate from current database schema:
  ```bash
  cd deployment
  docker-compose exec postgres pg_dump -U $POSTGRES_USER -d $POSTGRES_DB --schema-only > ../backend/database/init/01_schema.sql
  ```

### Reset Issues

**"database is being accessed by other users"**
- Cause: Backend or other connections still open
- Solution:
  ```bash
  cd deployment
  docker-compose exec postgres psql -U $POSTGRES_USER -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$POSTGRES_DB';"
  ```

**Init script fails with syntax error**
- Cause: SQL syntax error in init script
- Solution: Check error message, fix SQL in `backend/database/init/*.sql`

**"relation already exists"**
- Cause: Database wasn't fully dropped
- Solution:
  ```bash
  cd deployment
  docker-compose exec postgres psql -U $POSTGRES_USER -d $POSTGRES_DB -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
  ```

**Alembic version mismatch after reset**
- Cause: Forgot to stamp Alembic version
- Solution: Run `alembic stamp head`

## Reference Documentation

- Migration workflow: [migration.md](./migration.md)
- Reset workflow: [reset.md](./reset.md)
- Database migration rules: `backend/AGENTS.md` lines 62-82
- Three-way sync requirement: `backend/AGENTS.md` lines 66-71
- Model definition guidelines: `backend/AGENTS.md` lines 83-132
