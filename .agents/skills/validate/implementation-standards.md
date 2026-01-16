# Implementation Standards

Code modification checklist to ensure all required standards are met.

## When to Check

Check these standards:
- During code implementation (proactive)
- After modifying code but before marking task complete
- Before running validation tools
- Before committing

## Standards Checklist

### 1. API Call Validation

**Check**: If code involves API calls, is proper validation used?

**What to look for**:
- API endpoint handlers in `backend/app/api/`
- Request body parsing
- Response data validation
- External API calls

**Required**:
- **New code**: MUST use Pydantic schemas (backend) or proper validation
- **Old code being refactored**: RECOMMENDED to add validation

**Backend Example**:
```python
# ✅ Good - Using Pydantic validation
from pydantic import BaseModel

class LoginRequest(BaseModel):
    username: str
    password: str

@router.post("/login")
async def login(request: LoginRequest):
    # request is validated automatically
    ...
```

```python
# ❌ Bad - No validation
@router.post("/login")
async def login(request: dict):
    username = request.get("username")  # Unsafe!
    ...
```

**Frontend Example**:
```typescript
// ✅ Good - Type validation
interface LoginRequest {
  username: string;
  password: string;
}

function login(request: LoginRequest) {
  // TypeScript ensures type safety
}
```

### 2. Data Type Schema Definition

**Check**: If new data types are added, are corresponding schemas defined?

**What to look for**:
- New Pydantic models
- New database models
- New TypeScript interfaces
- New data structures

**Required**:
- **Backend**: Pydantic schemas in `backend/app/schemas/`
- **Frontend**: TypeScript interfaces in appropriate files
- **Database**: SQLAlchemy models in `backend/app/models/`

**Backend Example**:
```python
# ✅ Good - Schema defined
# In backend/app/schemas/user.py
class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    created_at: datetime
```

**Frontend Example**:
```typescript
// ✅ Good - Interface defined
// In frontend/wx-minipg/types/user.ts
interface User {
  id: number;
  username: string;
  email: string;
  createdAt: string;
}
```

### 3. Lint Error Fixes

**Check**: Are related lint errors fixed?

**What to look for**:
- Ruff errors in modified Python files
- ESLint errors in modified TypeScript files
- Mypy type errors
- Import order issues

**Required**:
- Fix all lint errors in files you modify
- Don't introduce new lint errors
- Run validation tools to verify

**How to check**:
```bash
# Backend
cd deployment
# Use validate skill

# Frontend
cd frontend/wx-minipg
npm run check
```

**Rule**: We improve code as we touch it. Even if errors exist in old code, fix them when you modify the file.

### 4. Documentation Updates

**Check**: Is related documentation updated?

**Documentation Update Rules**:

**API Changes** → Update `docs/api/*.md`
- Modified files in `backend/app/api/`
- Update request/response schemas
- Update error codes
- Update examples

**Database Schema Changes** → Update BOTH:
- `backend/database/init/*.sql` (init scripts)
- `docs/data-dict/*.md` (data dictionary)
- Modified files in `backend/app/models/` or `backend/alembic/versions/`
- Both must be synchronized (three-way sync)

**Feature/Business Logic Changes** → Update `docs/spec/*.md`
- Significant changes to business logic
- New features
- Behavior changes

**Architecture/Design Changes** → Update `AGENTS.md`
- Changes to system architecture
- Design decisions
- Module-specific `AGENTS.md` files

**Exceptions (No Documentation Needed)**:
- `docs/tasks/*.md` - Temporary task tracking
- Test files only changes
- Minor code formatting (no behavior change)
- Comment updates only

## File Pattern Mapping

Use these patterns to identify required documentation:

| Modified Files | Required Documentation |
|----------------|------------------------|
| `backend/app/api/**/*.py` | `docs/api/*.md` |
| `backend/app/models/*.py` | `docs/data-dict/*.md` + `backend/database/init/01_schema.sql` |
| `backend/alembic/versions/*.py` | `docs/data-dict/*.md` + `backend/database/init/*.sql` |
| `frontend/wx-minipg/pages/**/*` | Check if feature docs need update |
| `backend/app/core/config.py` | Check if config docs need update |
| `.env.example` | Update environment variable documentation |

## Verification Steps

### Step 1: Identify Modified Files

```bash
git status --short
git diff --name-only HEAD
```

### Step 2: Run Checklist for Each File

**Backend Python files** (`backend/app/**/*.py`):
- [ ] API validation check (if API endpoint)
- [ ] Schema definition check (if new data types)
- [ ] Lint errors check (always)
- [ ] Documentation check (if API/model/feature change)

**Frontend TypeScript files** (`frontend/wx-minipg/**/*.ts`):
- [ ] Type definition check (if new data types)
- [ ] Lint errors check (always)
- [ ] Documentation check (if feature change)

**Database models** (`backend/app/models/*.py`):
- [ ] Schema definition check (always)
- [ ] Lint errors check (always)
- [ ] Documentation check (always - data dict + init script)

### Step 3: Report Results

**✅ Checklist Passed**:
- List items properly implemented

**⚠️ Issues Found**:
- List items needing attention
- Provide specific file locations and suggestions

**Example Report**:
```
Implementation Standards Check:

Modified files: 3
- backend/app/api/auth.py
- backend/app/schemas/auth.py
- docs/api/auth.md

✅ Passed:
- API validation: Using Pydantic LoginRequest schema
- Schema definition: LoginRequest and LoginResponse defined
- Documentation: docs/api/auth.md updated

⚠️ Issues:
- Lint errors: backend/app/api/auth.py has 2 mypy errors
  → Line 45: Missing return type annotation
  → Line 67: Incompatible types in assignment
```

### Step 4: Block Completion if Issues Found

If any checklist items fail:
- **DO NOT** mark task as complete
- **DO NOT** proceed to commit
- Fix issues first, then re-run check

## Important Rules

1. **Run during implementation** - Don't wait until the end
2. **All items must pass** - No exceptions for "quick fixes"
3. **New code must be stricter** - Validation is mandatory for new API code
4. **Documentation is not optional** - Code without docs is incomplete

## Common Issues

### Issue: "I added API endpoint but forgot validation"

**Solution**: Add Pydantic model for request/response validation

### Issue: "I modified model but forgot to update data dict"

**Solution**: Run `/database` skill to sync all three sources (model, init script, data dict)

### Issue: "I have lint errors but they're in old code"

**Solution**: Fix them anyway - we improve code as we touch it

### Issue: "Documentation seems optional for small changes"

**Solution**: No - even small API changes need documentation updates

## Reference

- Code modification checklist: `AGENTS.md` lines 66-70
- Implementation process: `AGENTS.md` lines 63-75
- Documentation rules: `AGENTS.md` lines 82-91
