# Implementation Standards

Checklist for implementation-level quality gates.

## Mandatory Checks

1. API inputs/outputs use explicit validation schemas.
2. New data structures have explicit type/schema definitions.
3. All modified files pass lint/type checks from `/validate`.
4. Required documentation is updated with code changes.
5. Text files are UTF-8 without BOM and contain no garbled characters.

## Documentation Mapping

| Modified files | Required updates |
|---|---|
| `backend/app/api/**/*.py` | `docs/api/*.md` |
| `backend/app/models/*.py` | matching `backend/alembic/versions/*.py` |
| `backend/alembic/versions/*.py` | verify matching `backend/app/models/*.py` |
| `frontend/mp-weixin/pages/**/*` | related `docs/spec/**/*.md` if behavior changes |
| config/environment files | corresponding config docs |

## Execution

1. Detect modified files with git.
2. Apply mapping table to determine required docs.
3. Verify related docs are updated in the same change set.
4. Block completion when any required update is missing.

## Rules

1. No hidden compatibility fallback to mask errors.
2. No task completion with unresolved checklist items.
3. Treat documentation updates as required deliverables, not optional.
