# SAYS Project Overview

## Product Focus
- MVP-stage AI companion chat app that mimics real WeChat conversations; copy must avoid "AI/robot" wording and pursue human pacing, tone, and emotion.
- Solo developer workflow with AI assistance, so every change must stay aligned with docs under `docs/design`, `docs/data-dict`, `docs/api`, and `docs/tech`; flag spec gaps instead of inventing behavior.

## Architecture Snapshot
- **Backend**: FastAPI 3.12 stack under `backend/app`, exposed through Starlette Admin (`http://localhost:8000/qiao-dash/`, admin/admin123).
- **Database**: PostgreSQL 16 with Alembic migrations plus init SQL scripts in `backend/database/init/`; dockerized DB container `postgres_db_container` (5432).
- **LLM**: Doubao via the OpenAI-compatible SDK; prompts emphasize relationship context.
- **Messaging Transport**: LeanCloud IM is only a delivery channel; business logic stays in our services so the transport layer can be swapped later.
- **Frontends**: WeChat mini program (`frontend/wx-minipg`) is active; Flutter iOS app is planned; future clients must preserve the WeChat-like experience.
- **Config Management**: Immutable secrets live in environment variables, feature/runtime knobs are persisted in the `system_configs` table.
- **Auth**: Hybrid user auth (JWT plus token store) for non-admin clients.

## Deployment & Ops
- Docker Compose lives in `deployment/`; `.env` at repo root seeds container config.
- Backend container (`backend_container`) serves port 8000 with reload enabled; DB volume `says_dev_postgres_data` must be pruned to re-run init scripts.

## Conversation & Scoring Flow
1. Buffer short-term messages
2. Persist into `ai_contexts`
3. Resolve `ai_character`
4. Fetch `relationship_score`
5. Pick relationship data via `ai_style`
6. Apply relationship prompt/personality template
7. Merge system prompts and context
8. Call LLM
9. Run JSON Schema validation
10. Update relationship scores
11. Deliver reply through LeanCloud

## Relationship Model
- V1 Independent Bidirectional Offset algorithm, 0-1000 scale per dimension with `left_sensitivity`/`right_sensitivity` (-100 to 100) tuning continuous evolution.
