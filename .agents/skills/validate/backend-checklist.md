# Backend Validation Checklist

Detailed backend validation steps and troubleshooting.

## Configuration

**Read from**:
- `backend/pyproject.toml` - Ruff and Mypy configuration
- `backend/.contracts.yaml` - Lint-imports architecture rules
- `deployment/.env` - Environment variables

**Never hardcode**: Database names, paths, or configuration values.

## Validation Steps

### Step 1: Ensure Tools Available

**Option A: Use venv tools directly (Windows)**
```bash
./venv/Scripts/ruff.exe check backend/app
./venv/Scripts/mypy.exe backend/app
```

**Option B: Activate venv first**
```bash
# Windows PowerShell
./venv/Scripts/Activate.ps1

# Linux/Mac/Git Bash
source venv/bin/activate

# Then run tools
ruff check backend/app
```

**Option C: Use Python module execution**
```bash
python -m ruff check backend/app
python -m mypy backend/app
```

**If tools not found**:
```bash
pip install -r backend/app/requirements.txt
```

### Step 2: Ruff Format Check

Check code formatting:

```bash
ruff format --check backend/app
```

**If fails, auto-fix**:
```bash
ruff format backend/app
```

### Step 3: Ruff Lint Check

Check code quality:

```bash
ruff check backend/app
```

**If fails, auto-fix**:
```bash
ruff check --fix backend/app
```

**Common issues**:
- Unused imports → Auto-removed
- Line too long → Auto-wrapped
- Missing docstrings → Add manually

### Step 4: Mypy Type Check

Check type safety:

```bash
mypy backend/app
```

**Type Error Decision Flow**:

1. **Real type error?**
   - Yes → Fix code, add correct type annotations
   - No → Continue to step 2

2. **Framework limitation?** (e.g., Starlette Admin conflicts)
   - Yes → Add to `pyproject.toml` `[[tool.mypy.overrides]]`
   - No → Continue to step 3

3. **Missing type stubs?** (third-party library)
   - Yes → Add `ignore_missing_imports = true` in overrides
   - No → Continue to step 4

4. **Reasonable use of Any?** (external API, dynamic config)
   - Yes → Add `# type: ignore[error-code]` with reason comment
   - No → Refactor code design

**Example type ignore with reason**:
```python
# type: ignore[attr-defined]  # LeanCloud SDK doesn't provide type stubs
```

### Step 5: Lint-Imports (Architecture)

Check architecture compliance:

```bash
lint-imports
```

**Common violations**:
- Repository importing from Orchestrator
- API importing from Repository directly
- Circular dependencies

**Fix**: Refactor to follow layered architecture (see backend/AGENTS.md lines 25-43)

### Step 6: Local Imports Check

Verify imports are at file top:

```bash
# This is checked by ruff, no separate command needed
```

**Fix**: Move imports to top of file (except TYPE_CHECKING blocks)

## Common Backend Issues

### Issue: "greenlet_spawn has not been called"

**Cause**: Accessing ORM relationships without preloading in async context

**Solution**:
```python
# ❌ Bad
user = await session.get(User, user_id)
posts = user.posts  # Error!

# ✅ Good
from sqlalchemy.orm import selectinload

user = await session.get(
    User,
    user_id,
    options=[selectinload(User.posts)]
)
posts = user.posts  # Works!
```

### Issue: "Import should be at file top"

**Cause**: Import inside function or after code

**Solution**:
```python
# ❌ Bad
def my_function():
    import something

# ✅ Good
import something

def my_function():
    ...
```

### Issue: "Layer X cannot depend on layer Y"

**Cause**: Architecture violation

**Example**:
```python
# ❌ Bad - Repository importing from Orchestrator
# In backend/app/repositories/user.py
from backend.app.orchestrators.auth import AuthOrchestrator

# ✅ Good - Orchestrator importing from Repository
# In backend/app/orchestrators/auth.py
from backend.app.repositories.user import UserRepository
```

**Solution**: Follow dependency rules:
- API → Orchestrator → Repository → Model
- Lower layers cannot import from higher layers

### Issue: Docker container unhealthy

**Cause**: Database connection failed or backend crashed

**Check logs**:
```bash
cd deployment
docker-compose logs backend
```

**Common fixes**:
- Database not ready → Wait for postgres healthcheck
- Migration not applied → Run `alembic upgrade head`
- Environment variable missing → Check `deployment/.env`

## Reference

- Backend architecture: `backend/AGENTS.md` lines 23-48
- Type checking rules: `backend/AGENTS.md` lines 133-176
- Quality checks: `backend/AGENTS.md` lines 448-496
