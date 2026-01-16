---
name: validate
description: "Unified code validation workflow. Runs format, lint, type checks, and implementation standards. Actions: validate, check, lint, fix. Triggers: after code changes, before commit. Files: backend/**/*.py, frontend/wx-minipg/**/*"
---

# Validate

Comprehensive code validation for both backend and frontend. Checks formatting, linting, type safety, architecture compliance, and implementation standards.

## When to Use

Run this skill:
- After modifying any code (backend or frontend)
- Before creating a git commit
- When fixing errors or warnings
- When the user asks to "validate", "check", or "lint" code

## Quick Start

**Auto-detect and validate modified files**:
```bash
# The skill will automatically detect which files changed and run appropriate checks
```

**Validate specific component**:
- Backend only: Specify `--backend`
- Frontend only: Specify `--frontend`
- Full validation: No flags (default)

## Configuration

**Read from actual config files** (never hardcoded):
- Backend tools: `backend/pyproject.toml`, `backend/.contracts.yaml`
- Frontend tools: `frontend/wx-minipg/package.json`, `frontend/wx-minipg/.eslintrc.js`
- Environment: `deployment/.env`

## Validation Workflow

### Step 1: Detect Changes

Identify what needs validation:

```bash
git status --short
git diff --name-only HEAD
```

Categorize files:
- Backend: `backend/**/*.py`
- Frontend: `frontend/wx-minipg/**/*.{ts,js,wxml,wxss}`

### Step 2: Run Backend Validation

If backend files were modified, run backend checks.

**See**: [backend-checklist.md](./backend-checklist.md) for detailed backend validation steps.

**Quick summary**:
1. Ruff format check
2. Ruff lint check
3. Mypy type check
4. Lint-imports (architecture)
5. Local imports check

### Step 3: Run Frontend Validation

If frontend files were modified, run frontend checks.

**See**: [frontend-checklist.md](./frontend-checklist.md) for detailed frontend validation steps.

**Quick summary**:
1. TypeScript type check
2. ESLint
3. Stylelint
4. UI audit

### Step 4: Implementation Standards Check

Verify code follows implementation standards:

**For all code changes, check**:
1. **API Validation**: New API endpoints use proper validation (Pydantic/Zod)
2. **Type Definitions**: New data types have schemas/interfaces defined
3. **Documentation**: Related docs are updated (API docs, data dict, specs)
4. **No Lint Errors**: All lint/type errors in modified files are fixed

**See**: [implementation-standards.md](./implementation-standards.md) for details.

### Step 5: Report Results

**If all checks pass**:
```
✅ Validation passed
- Backend: All checks passed (ruff, mypy, lint-imports)
- Frontend: All checks passed (TypeScript, ESLint, Stylelint, UI audit)
- Implementation: All standards met
```

**If checks fail**:
```
❌ Validation failed
- [List specific errors with file:line references]
- [Provide fix suggestions]
```

## Auto-Fix Capabilities

The skill will attempt auto-fixes where possible:

**Backend**:
```bash
# Auto-fix formatting
ruff format backend/app

# Auto-fix lint issues
ruff check --fix backend/app
```

**Frontend**:
```bash
cd frontend/wx-minipg
npm run lint:fix
npm run format
```

## Important Rules

1. **All checks must pass** - Never report completion with failing checks
2. **Try auto-fix first** - Attempt automatic fixes before asking for help
3. **Verify fixes work** - Re-run validation after fixing
4. **Document why** - If using `# type: ignore`, explain the reason

## Common Issues

### Backend Issues

**"greenlet_spawn has not been called"**
- Cause: Accessing ORM relationships without preloading
- Fix: Use `.options(selectinload(...))` to preload relationships

**"Import should be at file top"**
- Cause: Import inside function
- Fix: Move import to file top (except TYPE_CHECKING blocks)

**"Layer X cannot depend on layer Y"**
- Cause: Architecture violation
- Fix: Refactor to follow dependency rules (see backend/AGENTS.md)

### Frontend Issues

**"Cannot find module"**
- Cause: Missing import or incorrect path
- Fix: Check import path, verify file exists

**"Property does not exist on type"**
- Cause: Missing type definition
- Fix: Define proper interface for Page data or Component properties

**UI Audit fails - hardcoded colors**
- Cause: Using hex colors instead of CSS variables
- Fix: Replace with TDesign variables (e.g., `#333` → `var(--td-text-color-primary)`)

## Reference Documentation

- Backend validation details: [backend-checklist.md](./backend-checklist.md)
- Frontend validation details: [frontend-checklist.md](./frontend-checklist.md)
- Implementation standards: [implementation-standards.md](./implementation-standards.md)
- Backend rules: `backend/AGENTS.md`
- Frontend rules: `frontend/wx-minipg/AGENTS.md`
