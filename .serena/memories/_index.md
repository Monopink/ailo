# Serena Memories Usage Guide

## Core Purpose
**Memories = Implementation Knowledge Base** (No duplication with docs)
- Docs = "What should be done" (Specifications)
- Memories = "How it's done" (Experience) + "Why it's done" (Decisions)

## File Index

| File | When to Read | Content |
|------|-------------|---------|
| **decisions.md** | Architecture design, major refactoring, tech selection | Core technical decisions with context |
| **known_issues.md** | Encountering errors, debugging | Known issues and solutions |
| **current_tasks.md** | Session start, cross-session tasks | Ongoing task contexts |
| **quick_ref.md** | Executing operations, finding configs | Commands, container names, ports, credentials |

## AI Behavior Rules

### Session Start
1. **Always** read `current_tasks.md` to check unfinished tasks
2. If user says "continue previous work", find task from current_tasks
3. Read other memories as needed based on task type

### During Task
- Error encountered → Read `known_issues.md` for solutions
- Architecture decision → Read `decisions.md` for design context
- Execute command → Read `quick_ref.md` for accurate info

### Session End
1. Cross-session task → Update `current_tasks.md`
2. Task completed → Delete from `current_tasks.md`
3. Found new issue → Add to `known_issues.md`
4. Major decision → Add to `decisions.md`

## Writing Standards

### ✅ Should Write
- 3rd-party library bugs and workarounds
- Docker/DB practical experiences
- Performance optimization test results
- Architecture decision context and trade-offs
- Environment-specific config differences

### ❌ Should NOT Write
- Code style rules (belongs to AGENTS.md)
- API definitions (belongs to docs/api/)
- Database schemas (belongs to docs/data-dict/)
- Feature design logic (belongs to docs/spec/)
- General programming principles (SOLID, KISS, etc.)

## Content Format
- **Minimal**: Lists, tables, keywords
- **Avoid long paragraphs**: Max 3 lines per paragraph
- **Direct expression**: Use imperative sentences
- **Version tagging**: Mark date/version for tech content
