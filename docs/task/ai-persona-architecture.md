# AI Persona & Instance Architecture Design

## Change Summary

- Inventory buckets are now defined by **AI types** (`ai_types`); personas, templates, and instances reference them via `type_id` instead of the old `ai_template_types` table.
- Square exposure moves to `square_type_entries`, which associate discovery slots directly with an `type_id` rather than a fixed `qiao_id`, keeping Square fully decoupled from inventory while relying on persona profiles for presentation.
- `ai_instances` persist the consumed `template_id` in addition to `persona_id`, `user_id`, and `user_qiao_id`; contact creation now happens in the same transaction that selects and consumes the template.
- Template/profile reusability still depends solely on `status` + `is_reusable`; the legacy `usage_status` field remains retired.
- `contact_requests` keep the expanded failure metadata (`failure_code`, `failure_detail`, `retry_count`, `last_retry_at`) plus `expires_at`, and a partial unique index on `(from_qiao_id, to_qiao_id)` for statuses `PENDING/PROCESSING` enforces idempotency.
- Runtime validation (admin form + API filtering) ensures every exposed persona has a backing `profiles` row without requiring hard foreign keys.

## Overview

The AI persona & instance system follows a three-layer inventory model:
1. **AI types** describe the internal product family (inventory bucket).
2. **Character profiles** bind each public `qiao_id` to one AI type and expose the persona through the global `profiles` table.
3. **Character instances** are user-specific contacts created from a template or via manual provisioning.

This document replaces the previous "template category" terminology, removes the legacy `usage_status` field, and introduces the resiliency features required for template shortages and Square decoupling.

## Core Principles

### Execution Guardrails

- All changes must land with the target architecture immediately—no temporary compatibility layers or incremental stopgaps.
- When trade-offs arise, choose the correct architecture over the smallest diff; refactors are encouraged if they simplify the long-term design.

### AI Types ≠ Square Categories

| Aspect | AI Types (`ai_types`) | Square Categories |
|--------|-----------------------|------------------|
| Purpose | Internal inventory and anti-duplication control | User-facing discovery buckets |
| Visibility | Admin only | Client only |
| Storage | Database table (`ai_types`) | Hardcoded enum + `square_type_entries` |
| Relationship | Groups character profiles and templates | Selects which `type_id` is surfaced in discovery |
| Ownership | Drives inventory, priority, cooldown | Drives recommendation strategy |

### qiao_id ↔ profile binding

- `qiao_id` is globally unique and always references a single `profiles` record.
- A character profile (`ai_personas`) must be created before any AI instance and is the **only** source of display information.
- Every user can only add a `qiao_id` once (contacts constraint); different users create independent `ai_instances` instances that still point to the same profile and template type.

### Inventory layering & reusability

- `is_reusable` defines whether a template/profile can be used by multiple users.
- `status` carries both visibility and consumption state:
  - `ai_templates.status`: `1=active`, `2=inactive`, `3=used` (single-use templates set to 3 after a successful assignment).
  - `ai_personas.status`: `1=active`, `2=inactive`, `3=used` (only for single-use personas).
  - `ai_instances.status`: `1=active`, `2=inactive`, `3=blocking` (AI blocked the user).
- `usage_count` is a pure statistic and never gates business logic.

### Template availability & concurrency

- Template selection must happen inside a database transaction that locks both the chosen template and the related profile row.
- `SELECT ... FOR UPDATE SKIP LOCKED` prevents the same single-use template from being assigned twice.
- Once a template is consumed, the worker immediately updates its `status` to 3 before creating the contact.

### Contact request idempotency & hang handling

- `contact_requests` now persist failure metadata so that pending requests can stay in place until inventory is replenished.
- Only one pending request per `(from_qiao_id, to_qiao_id)` exists; a duplicate submission triggers a retry instead of inserting a new row.
- Users never see a special error while a request is hanging; all UX feedback remains `{"message": "请求已发送"}`.

### Square decoupling

- Square recommendations read from `square_type_entries`, a dedicated table that maps discovery categories to an `type_id` without touching persona inventory directly; all card visuals come from the resolved persona/profile.
- Admin tooling validates that the selected AI type currently has at least one active persona + profile; the runtime API still filters out stale entries before returning them to clients.
- Entries are sampled randomly (or per configured strategy). Admin tooling controls status and entry groups for experimentation without storing additional payload blobs.

## Database Objects

### 1. `ai_types`

```sql
CREATE TABLE ai_types (
    id SERIAL PRIMARY KEY,
    display_name VARCHAR(100) NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

Key points:
- Internal-only. No Square coupling or `status` column.
- Serves as the parent for templates, personas, and type-level Square exposure entries.
- Uses `id` as the internal identifier; `display_name` for admin display.
- `display_name` replaces the previous `name`/internal key field but is not constrained to be unique.

### 2. `ai_personas`

```sql
CREATE TABLE ai_personas (
    id BIGINT PRIMARY KEY,
    qiao_id VARCHAR(32) NOT NULL UNIQUE,
    type_id INTEGER NOT NULL REFERENCES ai_types(id),
    is_reusable INTEGER NOT NULL DEFAULT 1,
    usage_count INTEGER NOT NULL DEFAULT 0,
    status INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

- Represents the SKU for a persona. Each profile has exactly one row in `profiles` with matching `owner_qiao_id` and `owner_type=2`.
- `status=3` means the persona was single-use and has already been consumed; the profile is automatically hidden from Square.
- All human-facing metadata (nickname, avatar, bio, etc.) lives in `profiles` and is never duplicated when creating `ai_instances`.

### 3. `ai_templates`

```sql
CREATE TABLE ai_templates (
    id SERIAL PRIMARY KEY,
    type_id INTEGER NOT NULL REFERENCES ai_types(id),
    style_id INTEGER NOT NULL,
    personality_id INTEGER NOT NULL,
    memory TEXT,
    prompt_variables JSONB,
    request_params JSONB,
    typing_speed_wpm INTEGER NOT NULL,
    display_name VARCHAR(100),
    position_mapping_config JSONB,
    is_reusable INTEGER NOT NULL DEFAULT 1,
    priority INTEGER NOT NULL DEFAULT 1,
    status INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

- Templates are the actual inventory that controls prompts, dimensions, and runtime overrides.
- Multiple templates can serve the same template type to provide redundancy or A/B variants.
- Single-use templates switch to `status=3` immediately after assignment.

### 4. `ai_instances`

```sql
CREATE TABLE ai_instances (
    id BIGINT PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id),
    user_qiao_id VARCHAR(32) NOT NULL,
    qiao_id VARCHAR(32) NOT NULL,
    type_id INTEGER NOT NULL REFERENCES ai_types(id),
    persona_id BIGINT NOT NULL REFERENCES ai_personas(id),
    template_id INTEGER REFERENCES ai_templates(id),
    style_id INTEGER NOT NULL,
    personality_id INTEGER NOT NULL,
    status INTEGER NOT NULL DEFAULT 1,
    memory TEXT,
    prompt_variables JSONB,
    relationship_id INTEGER,
    relationship_counts JSONB,
    request_params JSONB,
    typing_speed_wpm INTEGER NOT NULL,
    timezone VARCHAR(50) NOT NULL DEFAULT 'Asia/Shanghai',
    created_by INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, persona_id)
);
```

- Each row is a user-specific instance but references the global persona via `persona_id` and the consumed template via `template_id` (nullable when admins provision manually).
- `user_id`/`user_qiao_id` make the per-user ownership explicit, which keeps blocking/relationship state scoped to one contact.
- `type_id` is stored redundantly for analytics and guardrails; it must match the linked persona.
- Admins may create instances manually (without a template) by copying the base configuration but still have to set `persona_id` and `type_id` explicitly.

### 5. `profiles`

- Stores the visual identity for both humans and AI.
- `UNIQUE(owner_qiao_id, owner_type)` guarantees the `qiao_id` binding.
- When a new `ai_personas` row is created, the service must upsert the `profiles` row atomically to avoid dangling qiao_ids.

### 6. `contacts` & `contact_requests`

- `contacts` enforces `UNIQUE(user_id, contact_qiao_id)` so the same user cannot add one `qiao_id` twice (even across deletion/restore flows).
- `contact_requests` adds resiliency fields:
  - `failure_code` (e.g., `NO_TEMPLATE_AVAILABLE`, `MANUAL_PROVISION_REQUIRED`).
  - `failure_detail` (JSON payload describing missing AI type, qiao_id, etc.).
  - `retry_count` (system-managed counter for operational visibility).
  - `last_retry_at` (timestamp of the last automated or manual retry attempt).
  - `expires_at` (the record stops being reusable once expired).
- `UNIQUE(from_qiao_id, to_qiao_id) WHERE status IN (1,8)` guarantees at most one pending/processing request per pair; duplicates now lock-and-retry instead of inserting new rows.
- A duplicate POST for the same `(from_qiao_id, to_qiao_id)` will reuse the existing pending row, increment `retry_count`, and attempt to finish the workflow again.

### 7. `square_type_entries`

```sql
CREATE TABLE square_type_entries (
    id SERIAL PRIMARY KEY,
    square_category INTEGER NOT NULL,
    type_id INTEGER NOT NULL REFERENCES ai_types(id),
    exposure_strategy INTEGER NOT NULL DEFAULT 1,
    status INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(square_category, type_id)
);
```

- Acts as a decoupled lookup for Square discovery; entries only store classification/strategy and rely on persona profiles for the actual presentation.
- `square_category`: Integer enum (1=friend, 2=love, 3=talk, 4=bestie, 5=hobby) stored natively
+ `exposure_strategy`: Integer enum; only `random` (1) is supported today, so fixed/weighted strategies were removed
+ Each entry references an `type_id` instead of a fixed `qiao_id`. The runtime service fetches a persona for that type (ensuring a valid profile) before returning data to the client.
+ Random sampling is performed per category, and admins can pause exposure by setting `status=2` without touching the inventory tables.
+ The historical `last_featured_at` field was removed so the admin surface only controls category, strategy, and status.

## Data Flows

### 1. Admin: Provision Inventory

```
1. Create AI type (`ai_types`).
2. Create character profile (`ai_personas`).
   - System generates `qiao_id`.
   - System upserts the `profiles` row (owner_type=2, owner_qiao_id matches the profile).
3. Optionally create multiple templates (`ai_templates`) under the same template type.
```

Notes:
- The number of character profiles can exceed the number of templates to deliver variety in Square while still constraining actual inventory.
- Manual characters (no template) still need a profile + AI type to ensure inventory metadata is consistent.

### 2. User: Add AI Contact

```
1. User submits `POST /api/v1/contact-requests` with target `qiao_id`.
2. Contact service checks existing contacts/request rows for idempotency.
3. AI service loads the character profile by `qiao_id` -> obtains `type_id`.
4. Begin transaction:
   a. Lock the profile row (`FOR UPDATE`).
   b. Select a template with `FOR UPDATE SKIP LOCKED` (single-use first by priority, reusable second via round-robin/random strategy).
   c. Copy template configuration into a new `ai_instances` row (`type_id`, `persona_id`, `template_id`, etc.) and set `status=1`.
   d. Insert/ensure the `contacts` row inside the same transaction so contact creation is atomic with template consumption.
   e. Update `ai_templates.status=3` if `is_reusable=0`.
   f. Update `ai_personas.status=3` if `is_reusable=0`; always increment `usage_count`.
5. Commit transaction and emit CHAT_INFO for the applicant.
```

If step 4b finds **no template**, the service:
- Leaves the request in `status=PENDING`.
- Sets `failure_code='NO_TEMPLATE_AVAILABLE'`, `failure_detail={"type_id": X, "qiao_id": ...}`.
- Returns the standard success message to the user.

### 3. Template Shortage & Retry Workflow

```
1. Pending request with `failure_code` is surfaced in the admin “pending inventory” list.
2. Admin creates additional templates for the required AI type.
3. Admin triggers a retry (from contacts view or admin dashboard).
4. System increments `retry_count`, updates `last_retry_at`, clears `failure_code`, and reruns the creation flow.
5. Success → ACCEPTED and contact created.
6. Failure again → re-populate `failure_code`/`failure_detail` with the fresh reason so admin sees up-to-date diagnostics.
```

The request ID never changes. Users attempting to re-add the same `qiao_id` route to the existing pending row and simply enqueue another retry.

## Template Selection Algorithm

```python
from sqlalchemy import func, select

async def select_template(db: AsyncSession, type_id: int) -> Optional[AITemplate]:
    """Return a locked template row ready for consumption."""
    single_use_stmt = (
        select(AITemplate)
        .where(
            AITemplate.type_id == type_id,
            AITemplate.status == 1,
            AITemplate.is_reusable == 0,
        )
        .order_by(AITemplate.priority.asc(), AITemplate.id.asc())
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    template = await db.scalar(single_use_stmt)
    if template:
        return template

    reusable_stmt = (
        select(AITemplate)
        .where(
            AITemplate.type_id == type_id,
            AITemplate.status == 1,
            AITemplate.is_reusable == 1,
        )
        .order_by(AITemplate.priority.asc(), func.random())
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    return await db.scalar(reusable_stmt)
```

Usage guidelines:
- Always execute inside the same transaction that updates the template/profile/instance rows.
- After creating the instance, update `ai_templates.status` to 3 for single-use templates **before** committing.
- If the persona itself is single-use, also set its status to 3 before commit.

## Entity Relationships

```
ai_types (1) ──→ (N) ai_personas
ai_types (1) ──→ (N) ai_templates
ai_personas (1) ──→ (1) profiles (owner_qiao_id)
ai_personas (1) ──→ (N) ai_instances
ai_templates (1) ──→ (N) ai_instances (optional when admin creates manually)
users (1) ──→ (N) contacts
contacts (1) ──→ (1) ai_instances via qiao_id (for AI contacts)
square_type_entries (1) ──→ (1) ai_type exposure entry
```

## Square Data Flow

1. Admin selects which AI type should appear in each Square category by inserting rows into `square_type_entries`. The UI/service validates that the chosen type currently has at least one active persona + profile.
2. Square API fetches entries by `square_category`, randomizes (or applies the configured `exposure_strategy`), then resolves the actual persona by selecting a valid `qiao_id` for the returned `type_id`.
3. Removing exposure is as simple as setting `status=2` for that entry; this does not affect template or persona inventory.

## Implementation Checklist

- [x] Rename `ai_template_categories` → `ai_types` in SQL and documentation (follow-up migrations update ORM + FK references).
- [x] Enforce `FOREIGN KEY` links (`ai_templates`, `ai_personas`, `ai_instances`) to the new `ai_types` table.
- [x] Document status semantics (no `usage_status`).
- [x] Define transaction-safe template selection flow.
- [x] Add `square_type_entries` table (type-level exposure).
- [x] Extend `contact_requests` with failure metadata.
- [x] Add `user_id`/`user_qiao_id` columns plus uniqueness constraint to `ai_instances`.
- [x] Add `type_id` to `square_type_entries` and enforce persona/profile validation via admin/service logic (no DB FK).
- [x] Add partial unique index on `contact_requests (from_qiao_id, to_qiao_id)` for statuses 1/8.
- [ ] Update SQLAlchemy models & CRUD (follow-up code task).
- [ ] Implement retry endpoint + admin tooling (documented separately in `docs/task/contact-request-retry.md`).
- [ ] Wire Square API to the new table.

## Admin & API Updates

### Discovery Management

- 新建 "Discovery" 分类，承载 `square_type_entries` 维护界面：字段包括 `square_category`、`type_id`、`exposure_strategy`（整数枚举，当前仅 random）、`status`。
- 支持新增/编辑/下架/批量导入曝光条目；Square 卡片展示字段（昵称、文案、封面等）统一沿用 persona/profile 数据，后台不再维护额外 JSON。
- 后台操作需实时验证所选 `type_id` 至少有一个活跃 persona + profile，否则拒绝保存。
- 数据接口：`GET /admin/discovery/entries`、`POST /admin/discovery/entries`、`PATCH /admin/discovery/entries/{id}`，均操作 `square_type_entries`，与模板库存完全解耦。

### Contact Request Pending View

- 后台列表根据 `(status=1 AND failure_code IS NOT NULL)` 展示挂起申请，字段：`request_id`、`from_qiao_id`、`to_qiao_id`、`type_id`、`failure_code`、`failure_detail`、`retry_count`、`last_retry_at`、`expires_at`。
- 列表操作含 “重试” 按钮，调用 `POST /api/v1/contact-requests/{id}/retry` 重置失败字段并重新执行实例化流程。
- contacts 视图也需加入相同的 “重试” 操作，确保客服或管理员能直接处理挂起记录。

### API Changes

- 新增 `POST /api/v1/contact-requests/{id}/retry`（需要 admin/系统权限），逻辑：
  1. 校验请求 `status=PENDING` 且未过期；
  2. 清空 `failure_code`、`failure_detail`，`retry_count += 1`，`last_retry_at = NOW()`；
  3. 异步执行模板选择 → 实例化 → 联系人创建。
- Square API 改为读取 `square_type_entries`：`GET /api/v1/discovery?category=love&count=...` 返回 `type_id`（及基本位置信息），服务层随后挑选一个有效 `qiao_id` 并附带 persona/profile 数据，不再扫描模板或档案表。

## References

- `backend/database/init/01_schema.sql`
- `docs/development/contact-request-flow.md`
- `docs/task/contact-request-retry.md`
- `docs/prototype/database.md`
