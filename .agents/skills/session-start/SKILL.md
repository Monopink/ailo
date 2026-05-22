---
name: session-start
description: "Session initialization. Establish repo context (rules, current diff, relevant docs). Actions: initialize, load, check. Triggers: session start, new conversation, beginning work."
---

# Session Start

Establish repo context at the start of work.

## Required Sequence

1. Read repository `AGENTS.md`.
2. Check current working tree state (`git status --short`).
3. Identify relevant docs/spec/api files for the task and read only those.
4. If `.codegraph/` exists, check index health (`codegraph status`) and report readiness.
5. If `.codegraph/` is missing or unhealthy, report the issue and propose `codegraph init -i` or `codegraph sync`.

## Execution Rules

1. Always run this before implementation work.
2. Do not invent missing context.
3. Do not run full re-index unless the user approves.
4. Report only actionable context to the user.

## Output

Return a short session summary with:
- Current change scope
- Applicable constraints/rules discovered
- Relevant docs to consult next (if needed)
