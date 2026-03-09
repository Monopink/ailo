# Backend Validation Checklist

Run backend checks with project tools.

## Required Config

- `pyproject.toml`
- `.importlinter`
- `backend/.contracts.yaml`
- `deployment/.env`

## Validation Commands

Run in project root:

```bash
ruff format --check --config pyproject.toml backend/app
ruff check --config pyproject.toml backend/app
mypy backend/app
lint-imports --config .importlinter
```

If running in Docker, ensure `/backend/pyproject.toml` and `/backend/.importlinter` are mounted.

## Auto-Fix Sequence

If formatting or lint fails:

```bash
ruff format --config pyproject.toml backend/app
ruff check --fix --config pyproject.toml backend/app
```

Then rerun the full validation command set.

## Failure Handling

1. Type errors: fix annotations or configure strict overrides in `pyproject.toml`.
2. Import-layer violations: refactor to allowed dependency flow in `backend/AGENTS.md`.
3. ORM async preload issues: preload relationships before access.
4. Do not bypass failures with hidden fallback logic.

## Completion Criteria

- All four commands pass.
- No new lint/type errors in modified files.
- Architecture constraints remain valid.
