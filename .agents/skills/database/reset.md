# Database Reset Workflow

Reset database to clean state. This is destructive.

## Hard Gates

1. Require explicit user confirmation before any destructive command.
2. Abort if environment indicates production/prod.
3. Use official initialization script; do not improvise reset flow.

## Reset Steps

```bash
python scripts/deploy/provision.py --env dev --fresh --with-fixtures
```

## Verification

```bash
cd deployment
docker compose -f dev/compose.yaml exec postgres psql -U $POSTGRES_USER -d $POSTGRES_DB -c "\dt"
docker compose -f dev/compose.yaml ps postgres backend
```

## Rules

1. Never run reset without confirmation.
2. Never run reset on production-like targets.
3. If any step fails, stop and report exact failing command.
4. `--fresh` uses `down -v --remove-orphans` and can remove dev-only containers (for example `ngrok`/`dozzle`); restore them explicitly after reset when needed.
