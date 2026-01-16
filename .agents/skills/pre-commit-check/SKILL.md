---
name: pre-commit-check
description: "Pre-commit validation workflow. Orchestrates code validation, documentation sync checks, and database sync verification. Actions: validate, check, verify. Triggers: before git commit, when user says 'ready to commit'. Files: all modified files"
---

# Pre-Commit Check

Comprehensive pre-commit validation orchestrator. Runs all necessary checks before creating a git commit by coordinating other skills.

## When to Use

Run this skill:
- Before creating any git commit
- When the user says "ready to commit" or "check before commit"
- After completing a task and before running `/commit`
- As a final verification step

**Optional modes**:
- `--docs-only`: Only check documentation sync (skip code validation)
- `--quick`: Skip tests and only run essential checks

## Pre-Commit Workflow

### Step 1: Check Git Status

See what files have been modified:

```bash
git status --short
git diff --name-only HEAD
```

Categorize changes:
- Backend files: `backend/**/*.py`
- Frontend files: `frontend/wx-minipg/**/*.{ts,js,wxml,wxss}`
- Database files: `backend/app/models/*.py`, `backend/alembic/versions/*.py`, `backend/database/init/*.sql`
- Documentation: `docs/**/*.md`
- Configuration: `.env`, `*.json`, `*.yaml`

### Step 2: Run Code Validation

**Use the `/validate` skill** to check code quality.

The validate skill will automatically:
- Detect which files changed (backend/frontend)
- Run appropriate validation checks
- Attempt auto-fixes where possible
- Report results

**If validation fails**: Stop and fix errors before proceeding.

**See**: `.agents/skills/validate/SKILL.md` for validation details.

### Step 3: Check Documentation Sync

If code files were modified, verify documentation is updated.

#### 3.1: Determine Required Documentation

Based on modified files, check if documentation should be updated:

**Documentation Update Rules**:

1. **API Changes**
   - Triggers: Modified `backend/app/api/**/*.py`
   - Required: `docs/api/*.md`
   - Update request/response schemas, error codes

2. **Database Schema Changes**
   - Triggers: Modified `backend/app/models/*.py` or `backend/alembic/versions/*.py`
   - Required: `backend/database/init/*.sql` AND `docs/data-dict/*.md`
   - Both must be synchronized (three-way sync)

3. **Configuration Changes**
   - Triggers: Modified config/settings files
   - Required: Relevant documentation, environment variable docs

4. **Feature/Business Logic Changes**
   - Triggers: Significant changes to business logic or new features
   - Required: `docs/spec/*.md`, relevant AGENTS.md sections

5. **Architecture/Design Changes**
   - Triggers: Changes to system architecture or design decisions
   - Required: `AGENTS.md` or module-specific `AGENTS.md`

**Exceptions (No Documentation Needed)**:
- `docs/tasks/*.md` - Temporary task tracking files
- Test files only changes
- Minor code formatting or refactoring (no behavior change)
- Comment updates only

#### 3.2: File Pattern Mapping

| Modified Files | Required Documentation |
|----------------|------------------------|
| `backend/app/api/**/*.py` | `docs/api/*.md` |
| `backend/app/models/*.py` | `docs/data-dict/*.md` + `backend/database/init/01_schema.sql` |
| `backend/alembic/versions/*.py` | `docs/data-dict/*.md` + `backend/database/init/*.sql` |
| `frontend/wx-minipg/pages/**/*` | Check if feature docs need update |
| `backend/app/core/config.py` | Check if config docs need update |
| `.env.example` | Update environment variable documentation |

#### 3.3: Verify Documentation Was Updated

Check if corresponding documentation files were also modified:

```bash
git diff --name-only HEAD | grep "docs/"
```

Compare modified docs with required documentation checklist.

#### 3.4: Report Documentation Status

**✅ Documentation Updated**:
- List files where documentation was properly updated

**⚠️ Missing Documentation**:
- List files that need documentation but weren't updated
- Specify which documentation files need to be created/updated

**If documentation is missing**: Ask user if you should update it now. Do NOT proceed with commit if documentation is missing.

### Step 4: Verify Database Sync (if applicable)

If database models or migrations were modified, verify three-way sync:

1. **SQLAlchemy Models** (`backend/app/models/*.py`)
2. **Init Scripts** (`backend/database/init/01_schema.sql`)
3. **Data Dictionary** (`docs/data-dict/*.md`)

**Verification**:
- Read the modified model file
- Check if init script was updated
- Check if data dictionary was updated

**If out of sync**: Stop and update missing files. Consider using `/database` skill.

### Step 5: Run Tests (if applicable)

If test files exist and are relevant, run them:

```bash
# Backend tests
cd deployment
pytest tests/ -v

# Frontend tests (if configured)
cd frontend/wx-minipg
npm test
```

**If tests fail**: Fix the failures before committing.

### Step 6: Review Changes

Do a final review of all changes:

```bash
git diff HEAD
```

**Check for**:
- Debug code (console.log, print statements)
- Commented-out code that should be removed
- TODO comments that should be addressed
- Sensitive data (API keys, passwords)
- Unnecessary whitespace changes

### Step 7: Generate Pre-Commit Summary

Create a summary of what will be committed:

**Files modified**: [count] files
- Backend: [list key files]
- Frontend: [list key files]
- Database: [list schema changes]
- Documentation: [list updated docs]

**Validations passed**:
- ✅ Code validation (via /validate skill)
- ✅ Documentation sync verified
- ✅ Database sync verified (if applicable)
- ✅ Tests passed (if applicable)

**Ready to commit**: Yes/No

## Important Rules

1. **Never skip validation** - All checks must pass before allowing commit
2. **Stop on first failure** - Don't continue if any validation fails
3. **Verify documentation sync** - Code changes must have corresponding docs
4. **Check database three-way sync** - Models, init scripts, and docs must match
5. **Review before committing** - Always do a final review of changes

## Integration with Other Skills

This skill orchestrates other skills:
- **`/validate`**: For code quality checks (backend + frontend)
- **`/database`**: For database sync verification (if needed)

## Common Issues

### Issue: Code validation fails

**Cause**: Code doesn't meet quality standards

**Solution**: The `/validate` skill will attempt auto-fixes. If that fails, manually fix issues.

### Issue: Documentation out of sync

**Cause**: Code changed but docs weren't updated

**Solution**: Review Step 3 documentation checklist and update missing docs. Use `--docs-only` mode to re-check after updates.

### Issue: Database sync broken

**Cause**: Model changed but init script or data dict not updated

**Solution**: Run `/database` skill to sync all three sources.

### Issue: Tests fail unexpectedly

**Cause**: Code changes broke existing functionality

**Solution**: Review test failures, fix code or update tests if behavior change is intentional.

## Reference Documentation

- Code validation: `.agents/skills/validate/SKILL.md`
- Database operations: `.agents/skills/database/SKILL.md`
- Code modification checklist: `AGENTS.md` lines 66-70
- Documentation update rules: `AGENTS.md` lines 82-91
