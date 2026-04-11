---
name: schema-autogen
description: "Generate schema artifacts from Alembic migrations and migrated DB schema. Produces data-dict TSV outputs and init SQL. Actions: generate, check."
---

# Schema Autogen

Generate database schema artifacts from Alembic migrations and the migrated database schema.

## Purpose

- Keep schema source-of-truth in Alembic migrations.
- Generate AI-friendly schema artifacts with consistent structure.
- Avoid manual edits for schema dictionary outputs.

## Commands

1. Standard generation (recommended):

```bash
python scripts/schema/generate_schema_artifacts.py
```

2. Generate only data-dict TSV (skip SQL export):

```bash
python scripts/schema/generate_schema_artifacts.py --skip-sql-export
```

3. Container-first SQL export (default):

```bash
python scripts/schema/generate_schema_artifacts.py --sql-export-mode pg_dump_docker --postgres-container postgres
```

4. Custom output locations:

```bash
python scripts/schema/generate_schema_artifacts.py --data-dict-dir docs/data-dict --sql-output backend/database/init/sql/01_schema.sql
```

## Output Files

- `schema.tables.tsv`: table-level index
- `schema.columns.tsv`: column-level index
- `schema.constraints.tsv`: constraints and indexes
- `backend/database/init/sql/01_schema.sql`: init SQL exported by selected mode (default `pg_dump_docker`)

## Rules

1. Do not edit generated files manually.
2. Regenerate after migration changes.
3. Run `alembic upgrade head` before reflection (script does this by default unless `--skip-migrate` is set).
4. Prefer Docker-connected execution path for SQL export to avoid Alembic `--sql` offline-mode incompatibility in data migrations.
5. When running from host machine, provide a reachable `--database-url` (for example `localhost` mapping) if `DB_HOST=postgres` is only resolvable inside Docker network.
