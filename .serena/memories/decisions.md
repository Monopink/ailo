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

## Object Storage: Tencent COS + Dynamic URL Generation
**When**: Jan 2025, object storage implementation
**Context**: Avatar/media files need cloud storage with CDN
**Decision**: Tencent COS (S3-compatible) + backend proxy upload + dynamic URL generation
**Rationale**:
- Avoid WeChat mini-program CORS issues
- Pre-signed URLs for uploads, CDN URLs for public access
- Never store complete URLs, always generate dynamically

**CDN Configuration** (Updated 2026-01):
- **Primary source**: `system_configs.media_public_base_url` (runtime modifiable via admin)
- **Fallback**: `MEDIA_PUBLIC_BASE_URL` env var (bootstrap/emergency only)
- **Storage backend cached**: `@lru_cache` on startup, call `reload_storage_backend()` to refresh
- **Removed**: per-file `cdn_domain` field (was over-engineered)

**Implementation**:
- Upload via `/api/v1/media/upload` unified endpoint
- Frontend never accesses COS directly
- Public URL format: `{cdn_domain}/{object_key}`
- Private URL: Pre-signed with 5-min expiry

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

---

## Frontend Code Quality: Strict Rules + Visible Technical Debt
**When**: Dec 2025, code quality improvement initiative
**Context**: AI-driven development, need to prevent common mistakes
**Decision**: Strict ESLint rules + accept visible errors as technical debt
**Rationale**:
- Strict rules prevent AI from writing unsafe code
- Visible errors (not hidden) create continuous improvement pressure
- Gradual fix approach avoids blocking development

**Implementation**:
- TypeScript strict mode enabled
- ESLint rules: no-floating-promises, strict-boolean-expressions, complexity limits
- ~400 existing errors visible but not blocking
- New code must pass all checks
- Fix errors incrementally when modifying related code

**Key Rules**:
- Promise handling: Must await or .catch()
- Type safety: Explicit null checks, use ?? not ||
- Complexity: max 15 cyclomatic, max 100 lines/function

---

## Runtime Validation: Zod for API Responses
**When**: Dec 2025, code quality improvement initiative
**Context**: TypeScript only validates at compile time, need runtime safety
**Decision**: Zod for runtime validation + gradual adoption
**Rationale**:
- Prevent API data mismatch bugs
- TypeScript types erased at runtime
- AI often assumes API returns correct data

**Implementation**:
- New code must use Zod for critical APIs (auth, user data, messages)
- Optional for simple config APIs
- Gradual adoption: add validation when modifying code
- Schema definitions in utils/schemas.ts
- Validated API calls via utils/api-validated.ts

**Adoption Strategy**:
- Not enforced by tooling (too complex)
- Enforced by documentation + code review
- Multi-layer reminders: CLAUDE.md checklist + AGENTS.md examples + code comments
