# Scripts Documentation

This directory contains utility scripts for development, testing, and validation.

## Available Scripts

### 0. deploy/provision.py ⭐ (Fresh Provision)
**Purpose**: Provision infrastructure, migrations, bootstrap data, and optional fixtures in one command

**Usage**:
```bash
# Fresh dev provisioning (recommended for first setup)
python scripts/deploy/provision.py --env dev --fresh --with-fixtures

# Fresh staging provisioning
python scripts/deploy/provision.py --env staging --fresh

# Incremental provisioning on existing dev environment
python scripts/deploy/provision.py --env dev

# Apply env-specific SQL overrides on incremental runs (opt-in)
python scripts/deploy/provision.py --env staging --apply-env-overrides
```

**What it does**:
1. Runs infrastructure init script (`backend/database/init/init.sh`)
2. Runs `alembic upgrade head`
3. Runs bootstrap baseline (`backend/database/bootstrap/base.sql`)
4. Runs env bootstrap overrides (`backend/database/bootstrap/env/<env>.sql`) when `--fresh` or `--apply-env-overrides`
5. Optionally runs dev fixtures (`backend/database/bootstrap/seeds/dev.sql`)
6. Ensures backend service is up

**Rules**:
- `--with-fixtures` is only supported in `dev`
- `prod --fresh` requires `--allow-prod-fresh`
- Env-specific SQL (`bootstrap/env/<env>.sql`) runs only with `--fresh` by default.
- Use `--apply-env-overrides` to run env-specific SQL on non-fresh runs.
- `staging/prod` require `ADMIN_BOOTSTRAP_PASSWORD_HASH` (bcrypt hash) in deployment env files.
- Invite/entitlement required baseline data is seeded by Alembic migration `20260412_00` as the source of truth.
- Migration `20260412_00` also backfills missing `ai_contact_limit` entitlement accounts for existing users.
- `bootstrap/base.sql` only inserts missing shared defaults and does not overwrite existing operator-modified values.

---

### 1. check_docker.sh
**Purpose**: Check Docker container health status

**Usage**:
```bash
./scripts/check_docker.sh
```

**What it checks**:
- Docker daemon is running
- PostgreSQL container status and health
- Backend container status and health
- Backend API responsiveness (/health endpoint)
- Recent container logs

**Exit codes**:
- 0: All checks passed
- 1: One or more checks failed

---

### 2. run_tests.sh
**Purpose**: Run the backend test suite

**Usage**:
```bash
# Run all tests
./scripts/run_tests.sh

# Run fast tests only (exclude slow tests)
./scripts/run_tests.sh --fast

# Run with coverage report
./scripts/run_tests.sh --coverage

# Run with verbose output
./scripts/run_tests.sh --verbose
```

**Requirements**:
- pytest
- pytest-asyncio
- httpx
- pytest-cov (for coverage)

**Exit codes**:
- 0: All tests passed
- 1: One or more tests failed

---

### 3. validate.sh
**Purpose**: Run code quality checks

**Usage**:
```bash
# Check all files
./scripts/validate.sh

# Check only git-modified files (faster)
./scripts/validate.sh --quick
```

**What it checks**:
1. Syntax validation (py_compile)
2. Jinja template syntax validation (admin templates)
3. Import location check (no local imports)
4. Code formatting (Ruff format)
5. Code quality (Ruff lint)
6. Type checking (mypy)
7. Architecture contracts (import-linter)

**Exit codes**:
- 0: All checks passed
- 1: One or more checks failed

---

### 4. full_check.sh ⭐ (Recommended)
**Purpose**: Complete system validation (Docker + Code + Tests)

**Usage**:
```bash
# Full validation (recommended before commit)
./scripts/full_check.sh

# Quick validation (modified files only)
./scripts/full_check.sh --quick

# Skip Docker health check
./scripts/full_check.sh --skip-docker

# Skip tests
./scripts/full_check.sh --skip-tests
```

**What it does**:
1. Runs Docker health check
2. Runs code quality validation
3. Runs test suite

**Exit codes**:
- 0: All validations passed
- 1: One or more validations failed

---

### 5. check_jinja_templates.py
**Purpose**: Validate Jinja syntax for Admin HTML templates

**Usage**:
```bash
# Check all admin templates
python scripts/check_jinja_templates.py

# Check specific templates
python scripts/check_jinja_templates.py backend/app/admin/templates/custom_views/ai_personality_advanced_edit.html
```

**Exit codes**:
- 0: All templates are valid
- 1: Syntax errors found

---

## Recommended Workflow

### For AI Development

After making code changes, run:

```bash
# Quick validation (recommended)
./scripts/full_check.sh --quick
```

This will:
- ✅ Check Docker containers are healthy
- ✅ Validate code quality (modified files only)
- ✅ Run fast tests

### Before Committing

```bash
# Full validation
./scripts/full_check.sh
```

This ensures everything is working correctly.

### For Fresh Environment Setup

```bash
python scripts/deploy/provision.py --env dev --fresh --with-fixtures
```

### Debugging Issues

If validation fails:

1. **Docker issues**:
   ```bash
   ./scripts/check_docker.sh
   ```
   Check the output for specific container problems.

2. **Code quality issues**:
   ```bash
   ./scripts/validate.sh --quick
   ```
   Fix reported issues one by one.

3. **Test failures**:
   ```bash
   ./scripts/run_tests.sh --verbose
   ```
   Review test output for specific failures.

---

## Script Permissions

On Unix-like systems, ensure scripts are executable:

```bash
chmod +x scripts/*.sh
```

On Windows, use Git Bash or WSL to run these scripts.

---

## Troubleshooting

### "Docker is not running"
- Start Docker Desktop
- Wait for Docker to fully initialize

### "Container not found"
- Start containers: `docker compose -f deployment/dev/compose.yaml up -d`

### "pytest not found"
- Install dependencies: `pip install -r backend/app/requirements-dev.txt`
- Install test dependencies: `pip install pytest pytest-asyncio httpx pytest-cov`

### "Tests fail with database errors"
- Ensure Docker containers are running
- Check database initialization completed
- Verify `.env` file configuration

---

## Adding New Tests

1. Create test file in `backend/tests/`:
   ```python
   # backend/tests/test_feature.py
   import pytest
   from httpx import AsyncClient

   @pytest.mark.asyncio
   async def test_my_feature(client: AsyncClient):
       response = await client.get("/api/v1/endpoint")
       assert response.status_code == 200
   ```

2. Run tests:
   ```bash
   ./scripts/run_tests.sh
   ```

3. Verify with full check:
   ```bash
   ./scripts/full_check.sh --quick
   ```

---

## CI/CD Integration

These scripts are designed to be CI/CD friendly:

```yaml
# Example GitHub Actions workflow
- name: Run validation
  run: ./scripts/full_check.sh

- name: Run tests with coverage
  run: ./scripts/run_tests.sh --coverage
```

---

## Notes

- All scripts use colored output for better readability
- Scripts continue on error to show all issues
- Exit codes follow Unix conventions (0 = success, 1 = failure)
- Scripts are idempotent and safe to run multiple times
