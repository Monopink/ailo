---
name: session-start
description: "Session initialization. Load memories (current_tasks, known_issues, decisions, quick_ref). Actions: initialize, load, check. Triggers: session start, new conversation, beginning work."
---

# Session Start

Load project memory context at the start of work.

## Required Sequence

1. Read `current_tasks`.
2. Read `known_issues`.
3. Read `decisions`.
4. Read `quick_ref`.
5. Read `_index`.

## Execution Rules

1. Always run this before implementation work.
2. If one memory is missing, continue with the rest.
3. Do not invent missing context.
4. Report only actionable context to the user.

## Output

Return a short session summary with:
- Current active tasks
- Relevant known risks
- Applicable architecture constraints
- Key command/operation reminders
