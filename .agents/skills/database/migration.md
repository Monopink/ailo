# Database Migration Workflow

Use this protocol after schema model changes.

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
3. Generate schema artifacts from source-of-truth models/migrations.
4. Ensure generated outputs include:
   - `backend/database/init/sql/01_schema.sql`
   - `docs/data-dict/*`
5. Verify single-source sync (models+migrations -> generated SQL/data-dict).

## Verification

```bash
cd deployment
docker compose -f dev/compose.yaml exec backend alembic upgrade head
docker compose -f dev/compose.yaml exec postgres psql -U $POSTGRES_USER -d $POSTGRES_DB -c "\d+"
```

## Rules

1. Use descriptive migration names.
2. Do not skip migration review.
3. Do not finish with unsynced generated artifacts.
4. If migration fails, fix migration or schema files before continuing.
