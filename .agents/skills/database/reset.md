# Database Reset Workflow

Reset database to clean state. This is destructive.

## Hard Gates

1. Require explicit user confirmation before any destructive command.
2. Abort if environment indicates production/prod.
3. Use official initialization script; do not improvise reset flow.

## Reset Steps

```bash
cd deployment
docker compose -f dev/compose.yaml stop backend
docker compose -f dev/compose.yaml exec postgres psql -U $POSTGRES_USER -c "DROP DATABASE IF EXISTS $POSTGRES_DB;"
docker compose -f dev/compose.yaml exec postgres psql -U $POSTGRES_USER -c "CREATE DATABASE $POSTGRES_DB;"
docker compose -f dev/compose.yaml exec postgres bash /docker-entrypoint-initdb.d/00_init_database.sh
docker compose -f dev/compose.yaml exec backend alembic stamp head
docker compose -f dev/compose.yaml start backend
```

## Verification

```bash
cd deployment
docker compose -f dev/compose.yaml exec postgres psql -U $POSTGRES_USER -d $POSTGRES_DB -c "\dt"
docker compose -f dev/compose.yaml ps backend
```

## Rules

1. Never run reset without confirmation.
2. Never run reset on production-like targets.
3. If any step fails, stop and report exact failing command.
