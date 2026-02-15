# Database Migration Workflow

Use this protocol after schema model changes.

## Precheck

1. Read DB config from `deployment/.env`.
2. Confirm changed model files with git diff.

## Migration Steps

1. Generate migration:

```bash
cd deployment
docker-compose exec backend alembic revision --autogenerate -m "descriptive_message"
```

2. Review generated file under `backend/alembic/versions/`.
3. Update init SQL to final schema state in `backend/database/init/`.
4. Update related tables in `docs/data-dict/`.
5. Verify three-way sync (model, init SQL, data dictionary).

## Verification

```bash
cd deployment
docker-compose exec backend alembic upgrade head
docker-compose exec postgres psql -U $POSTGRES_USER -d $POSTGRES_DB -c "\d+"
```

## Rules

1. Use descriptive migration names.
2. Do not skip migration review.
3. Do not finish with unsynced schema/docs.
4. If migration fails, fix migration or schema files before continuing.
