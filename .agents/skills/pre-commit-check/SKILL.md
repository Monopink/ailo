---
name: pre-commit-check
description: "Pre-commit validation workflow. Orchestrates code validation, documentation sync checks, and database sync verification. Actions: validate, check, verify. Triggers: before git commit, when user says 'ready to commit'. Files: all modified files"
---

# Pre-Commit Check

Run final commit gate checks by orchestrating project skills.

## Workflow

1. Detect change scope:
   - `git status --short`
   - Prefer using `git diff --name-only --cached` to scope what will be committed.
2. Run `/validate`.
3. Verify documentation sync using `.agents/skills/validate/implementation-standards.md`.
4. If database schema changed, verify `backend/alembic/versions/*.py` as single source-of-truth and confirm model alignment, or run `/database`.
5. Run encoding gates:
   - `pre-commit run fix-byte-order-marker --all-files`
   - `pre-commit run check-text-encoding --all-files`
6. Run relevant tests when present.
7. Review final diff for debug code and sensitive output.
8. Return commit readiness.

## Stop Conditions

Stop immediately and block commit when:
- Any validation command fails.
- Encoding hooks report non-UTF-8, BOM, replacement characters, or garbled text patterns.
- Required documentation updates are missing.
- Database source-to-artifact sync is broken.
- Tests fail.
- Project virtual environment is unavailable or validation tools are missing inside it.

## Output

Return:
- Modified file summary
- Validation and test results
- Documentation/database sync status
- `Ready to commit: Yes/No`
