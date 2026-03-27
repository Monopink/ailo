# Backend Validation Checklist

Run backend checks with project tools.

## Required Config

- `pyproject.toml`
- `.importlinter`
- `backend/.contracts.yaml`
- `deployment/.env`
- Project virtual environment (`venv`)

## Environment Precheck (Mandatory)

1. Confirm project interpreter first (example on Windows):
   - `venv\\Scripts\\python.exe -V`
2. Confirm required tools are available in this interpreter:
   - `venv\\Scripts\\python.exe -m ruff --version`
   - `venv\\Scripts\\python.exe -m mypy --version`
   - `venv\\Scripts\\python.exe -m pytest --version`
3. If any command fails, stop and report environment issue to user.
4. Do not use global `python`, global `pytest`, or globally installed lint tools as fallback.

## Validation Commands

Run in project root:

```bash
venv\Scripts\python.exe -m ruff format --check --config pyproject.toml backend/app
venv\Scripts\python.exe -m ruff check --config pyproject.toml backend/app
venv\Scripts\python.exe -m mypy backend/app
set PYTHONPATH=backend&& venv\Scripts\lint-imports.exe --config .importlinter
```

For Linux/macOS shells, use:
- `PYTHONPATH=backend venv/bin/lint-imports --config .importlinter`

If running in Docker, ensure `/backend/pyproject.toml` and `/backend/.importlinter` are mounted.

## Database Health Precheck (Before DB-Dependent Tests)

1. Validate service status:
   - `docker ps --format "{{.Names}}|{{.Status}}|{{.Ports}}"`
2. Validate PostgreSQL readiness:
   - `docker exec postgres pg_isready -U ailo_user -d ailo`
3. Prefer running DB-dependent tests inside `backend` container:
   - `docker exec backend python -m pytest /backend/tests/<target>.py`
4. If host-side tests fail with connection errors while containers are healthy, treat as host networking/runtime issue and report clearly.

## Auto-Fix Sequence

If formatting or lint fails:

```bash
venv\Scripts\python.exe -m ruff format --config pyproject.toml backend/app
venv\Scripts\python.exe -m ruff check --fix --config pyproject.toml backend/app
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
