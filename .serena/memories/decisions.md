# Core Technical Decisions

## Strict Layered Architecture
**When**: Early 2024, initial project setup
**Context**: MVP stage, solo developer, need clear boundaries
**Decision**: API → Service → Data/CRUD → Model
**Rationale**:
- Prevent cross-layer chaos
- Service layer independently testable
- Easy horizontal scaling later

**Constraints**:
- Services must NOT directly manipulate Models
- APIs must NOT directly call CRUD
- Complex queries in services/*/data/, basic CRUD in crud/

---

## Messaging: Transport Layer Only
**When**: Mid 2024
**Context**: Need realtime IM, avoid vendor lock-in
**Decision**: Business logic in backend, LeanCloud only delivers messages
**Rationale**:
- Future switch to self-hosted WebSocket/other IM possible
- Relationship scoring, AI dialogue logic vendor-agnostic
- Lower migration cost

**Implementation**:
- All dialogue logic in services/ai/
- LeanCloud SDK only in services/message/outbound/
- Don't use LeanCloud's conversation history storage

---

## Config: Dual-Track Management
**When**: Early 2024
**Context**: MVP stage, frequent config changes
**Decision**:
- Immutable secrets (DB password, API keys) → Env vars
- Adjustable configs (AI params, feature flags) → system_configs table

**Rationale**:
- Avoid container restart for config changes
- Admin panel can adjust runtime params
- Clear separation of "deployment config" vs "business config"

---

## Object Storage: Self-Hosted MinIO
**When**: Jan 2025, object storage migration
**Context**: Avatar/media files need independent storage
**Decision**: MinIO (S3-compatible) + backend proxy upload
**Rationale**:
- Avoid WeChat mini-program CORS issues
- Pre-signed URLs unstable in WeChat env
- Seamless future switch to AWS S3/Aliyun OSS

**Implementation**:
- Upload via /api/v1/media/upload unified
- Frontend never accesses MinIO directly
- URL format: /api/v1/media/{object_key}

---

## Auth: JWT + Token Store Hybrid
**When**: Early 2024
**Context**: Need token revocation capability
**Decision**: JWT stores user info + token_store table manages lifecycle
**Rationale**:
- JWT cannot be actively invalidated, needs DB support
- Supports "kick out login", "device limit"
- refresh_token managed independently for security

---

## Relationship Scoring: Independent Bidirectional Offset Algorithm V1
**When**: Mid 2024, AI dialogue design
**Context**: Need to simulate dynamic human relationship changes
**Decision**: 0-1000 score + left/right_sensitivity(-100~100)
**Rationale**:
- Bidirectional independence: A's affection to B ≠ B's affection to A
- Sensitivity: Personality affects relationship change speed
- Continuous evolution: Avoid discrete "relationship levels"

**Formula**:
```
new_score = old_score + delta * (1 + sensitivity/100)
```
