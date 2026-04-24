# Database Migration Workflow

Use this protocol for schema changes.

## Precheck

1. Read DB config from `deployment/.env`.
2. Confirm changed model files using `git status --short`. Only use `git diff --name-only --cached` when you specifically need the staged file list.

## Migration Steps

1. Generate migration:

```bash
cd deployment
docker compose -f dev/compose.yaml exec backend alembic revision --autogenerate -m "descriptive_message"
```

2. Review generated file under `backend/alembic/versions/`.
3. Keep init/bootstrap responsibilities aligned:
   - `backend/database/init/init.sh`: infra only
   - `backend/database/bootstrap/base.sql` + `backend/database/bootstrap/env/*.sql`: environment baseline business data
   - `backend/database/bootstrap/seeds/dev.sql`: dev/test fixtures only
4. Verify single-source sync (`backend/alembic/versions/*.py`), and confirm model definitions are aligned.

## Verification

```bash
cd deployment
docker compose -f dev/compose.yaml exec backend alembic upgrade head
docker compose -f dev/compose.yaml exec postgres psql -U $POSTGRES_USER -d $POSTGRES_DB -c "\d+"
python scripts/deploy/provision.py --env dev
```

## Rules

1. Use descriptive migration names.
2. Do not skip migration review.
3. Do not finish with unsynced model/migration definitions.
4. If migration fails, fix migration or schema files before continuing.
5. Never use `--fresh` in migration verification unless the user explicitly requests a destructive reset.
