---
name: schema-autogen
description: "Generate schema artifacts from SQLAlchemy models. Produces AI-oriented data-dict TSV outputs and optional SQL preview. Actions: generate, preview, check."
---

# Schema Autogen

Generate database schema artifacts from SQLAlchemy models.

## Purpose

- Keep schema source-of-truth in models.
- Generate AI-friendly schema artifacts with consistent structure.
- Avoid manual edits for schema dictionary outputs.

## Commands

1. Preview generation (safe, no overwrite):

```bash
python scripts/schema/generate_schema_artifacts.py --output-dir docs/plans/schema-autogen-preview
```

2. TSV-only generation (for replacing docs/data-dict):

```bash
python scripts/schema/generate_schema_artifacts.py --output-dir docs/data-dict --no-sql-preview
```

3. Optional custom SQL filename:

```bash
python scripts/schema/generate_schema_artifacts.py --output-dir docs/plans/schema-autogen-preview --sql-filename 01_schema.preview.sql
```

## Output Files

- `schema.tables.tsv`: table-level index
- `schema.columns.tsv`: column-level index
- `schema.constraints.tsv`: constraints and indexes
- `01_schema.preview.sql`: optional SQL preview from metadata

## Rules

1. Do not edit generated files manually.
2. Regenerate after model changes.
3. Use preview directory first; replace runtime files only after review/approval.
