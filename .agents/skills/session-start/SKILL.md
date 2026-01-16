---
name: session-start
description: "Session initialization. Load memories (current_tasks, known_issues, decisions, quick_ref). Actions: initialize, load, check. Triggers: session start, new conversation, beginning work."
---

# Session Start

Initialize a new work session by loading context from Serena memories. Helps AI understand ongoing tasks, avoid known issues, and follow established decisions.

## When to Use

Run this skill:
- At the beginning of every new conversation/session
- When the user says "start", "begin", or "initialize"
- Before starting any significant work
- When you need to understand the project context

## Initialization Steps

### Step 1: Read Current Tasks

Load the current tasks memory to understand what's in progress:

```
Read memory: current_tasks.md
```

This tells you:
- What tasks are currently in progress
- What tasks are pending
- What was completed recently
- Task priorities and dependencies

### Step 2: Read Known Issues

Load the known issues memory to avoid repeating mistakes:

```
Read memory: known_issues.md
```

This tells you:
- Common errors and their solutions
- Known bugs and workarounds
- Things that don't work and why
- Pitfalls to avoid

### Step 3: Read Architecture Decisions

Load the decisions memory to understand architectural choices:

```
Read memory: decisions.md
```

This tells you:
- Key architectural decisions made
- Why certain approaches were chosen
- What alternatives were rejected and why
- Design principles to follow

### Step 4: Read Quick Reference

Load the quick reference memory for common commands and configurations:

```
Read memory: quick_ref.md
```

This tells you:
- Frequently used commands
- Common configuration values
- Shortcuts and tips
- Quick troubleshooting steps

### Step 5: Read Memory Index

Load the memory index to understand the memory system:

```
Read memory: _index
```

This tells you:
- How the memory system is organized
- What other memories are available
- Memory usage guidelines

### Step 6: Summarize Context

After reading all memories, provide a brief summary to the user:

**Session Context Summary:**
- 📋 Current Tasks: [Number] tasks in progress, [Number] pending
- ⚠️ Known Issues: [Number] issues to be aware of
- 🏗️ Key Decisions: [Brief mention of important architectural decisions]
- 💡 Quick Tips: [Any relevant quick reference items]

Ask the user: "What would you like to work on today?"

## Handling Missing Memories

If any memory file doesn't exist or is empty:
- Note which memories are missing
- Continue with available memories
- Don't treat it as an error

## Important Rules

1. **Always run at session start** - This should be the first thing you do
2. **Read all available memories** - Don't skip any of the core memories
3. **Summarize for the user** - Provide a clear context summary
4. **Don't fail on missing memories** - Some memories may not exist yet

## Core Memories to Load

Priority order:
1. `current_tasks.md` - Most important, tells you what to work on
2. `known_issues.md` - Critical, prevents repeating mistakes
3. `decisions.md` - Important, guides architectural choices
4. `quick_ref.md` - Helpful, provides shortcuts
5. `_index` - Reference, explains the memory system

## Reference Documentation

- Memory usage guidelines: `AGENTS.md` lines 98-106
- Serena MCP documentation: `AGENTS.md` lines 94-106
