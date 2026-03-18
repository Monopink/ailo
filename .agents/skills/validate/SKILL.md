---
name: validate
description: "Unified code validation workflow. Runs format, lint, type checks, and implementation standards. Actions: validate, check, lint, fix. Triggers: after code changes, before commit. Files: backend/**/*.py, frontend/mp-weixin/**/*"
---

# Validate

Run project validation after code changes and before commit.

## Workflow

1. Detect modified files:
   - `git status --short`
   - Prefer deriving the changed file list from `git status --short`.
   - Only use `git diff --name-only --cached` when you specifically need the staged file list for a commit gate.
2. If backend files changed, run [backend-checklist.md](./backend-checklist.md).
3. If frontend files changed, run [frontend-checklist.md](./frontend-checklist.md).
4. Run [implementation-standards.md](./implementation-standards.md).
5. Re-run checks after every auto-fix.
6. Return pass/fail with file-level errors.

## Rules

1. Use configured project tools, not manual lint logic.
2. Do not claim completion while any check fails.
3. If `# type: ignore` is added, include an inline reason.
4. Keep validation scoped to changed files when possible.

## Sources of Truth

- Backend config: `backend/pyproject.toml`, `backend/.contracts.yaml`
- Frontend config: `frontend/mp-weixin/package.json`, `frontend/mp-weixin/.eslintrc.js`
- Project rules: `backend/AGENTS.md`, `frontend/mp-weixin/AGENTS.md`
