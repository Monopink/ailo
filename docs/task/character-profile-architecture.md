# AI Character Profile Architecture Design

## Change Summary

- Template categories renamed to **template types** (`ai_template_types`), fully detached from Square categories.
- `qiao_id` is permanently bound to `profiles`, while templates and character instances reference it through `ai_personas`.
- Template/profile reusability now depends solely on `status` + `is_reusable`; the old `usage_status` logic is retired.
- `contact_requests` persist failure metadata (`failure_code`, `failure_detail`, `retry_count`, `last_retry_at`) to support hang + retry.
- Square exposure is managed by `square_character_entries`, with random discovery managed independently from template inventory.
- `ai_instances` now persist `user_id` + `user_qiao_id` so each record truly represents one user's instance of a persona; contacts creation and template consumption run inside the same transaction.
- `square_character_entries` store `template_type_id` and rely on runtime validation (admin form + API filtering) to ensure each `qiao_id` has an associated `profiles` row before exposure.
- A partial unique index on `contact_requests (from_qiao_id, to_qiao_id)` ensures at most one PENDING/PROCESSING row per pair while the retry metadata keeps operational visibility.

## Overview

The AI character system follows a three-layer inventory model:
1. **Template types** describe the internal product family (inventory bucket).
2. **Character profiles** bind each public `qiao_id` to one template type and expose the persona through the global `profiles` table.
3. **Character instances** are user-specific contacts created from a template or via manual provisioning.

This document replaces the previous "template category" terminology, removes the legacy `usage_status` field, and introduces the resiliency features required for template shortages and Square decoupling.

## Core Principles

### Execution Guardrails

- All changes must land with the target architecture immediately—no temporary compatibility layers or incremental stopgaps.
- When trade-offs arise, choose the correct architecture over the smallest diff; refactors are encouraged if they simplify the long-term design.

### Template Types ≠ Square Categories

| Aspect | Template Types (`ai_template_types`) | Square Categories |
|--------|-------------------------------------|------------------|
| Purpose | Internal inventory and anti-duplication control | User-facing discovery buckets |
| Visibility | Admin only | Client only |
| Storage | Database table (`ai_template_types`) | Hardcoded enum + `square_character_entries` |
| Relationship | Groups character profiles and templates | Maps `qiao_id` to discovery surfaces |
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

- Square recommendations read from `square_character_entries`, a dedicated table that maps discovery categories to `qiao_id` without touching the inventory tables.
- Each entry stores `template_type_id`; admin tooling validates that the `qiao_id` already has a `profiles` row, but the database stays decoupled (no FK) and Square APIs filter out any dangling entries at runtime.
- Entries are sampled randomly (no sorting). Admin tooling controls status/metadata for experimentation.

## Database Objects

### 1. `ai_template_types`

```sql
CREATE TABLE ai_template_types (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    display_name VARCHAR(100) NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

Key points:
- Internal-only. No Square coupling.
- Serves as the parent for both templates and character profiles.
- No `status` column—availability is entirely dictated by the linked templates/profiles.

### 2. `ai_personas`

```sql
CREATE TABLE ai_personas (
    id BIGINT PRIMARY KEY,
    qiao_id VARCHAR(32) NOT NULL UNIQUE,
    template_type_id INTEGER NOT NULL REFERENCES ai_template_types(id),
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
    template_type_id INTEGER NOT NULL REFERENCES ai_template_types(id),
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
CREATE TABLE ai_characters (
    id BIGINT PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id),
    user_qiao_id VARCHAR(32) NOT NULL,
    qiao_id VARCHAR(32) NOT NULL,
    template_type_id INTEGER NOT NULL REFERENCES ai_template_types(id),
    character_profile_id BIGINT NOT NULL REFERENCES ai_personas(id),
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
    UNIQUE (user_id, character_profile_id)
);
```

- Each row is a user-specific instance but references the global profile via `character_profile_id`.
- `user_id`/`user_qiao_id` make the per-user ownership explicit, which keeps blocking/relationship state scoped to one contact.
- `template_type_id` is stored redundantly for easier analytics; it must match the linked profile.
- Admins may create characters manually (without a template) by copying the base configuration but still have to set `character_profile_id` and `template_type_id` explicitly.

### 5. `profiles`

- Stores the visual identity for both humans and AI.
- `UNIQUE(owner_qiao_id, owner_type)` guarantees the `qiao_id` binding.
- When a new `ai_personas` row is created, the service must upsert the `profiles` row atomically to avoid dangling qiao_ids.

### 6. `contacts` & `contact_requests`

- `contacts` enforces `UNIQUE(user_id, contact_qiao_id)` so the same user cannot add one `qiao_id` twice (even across deletion/restore flows).
- `contact_requests` adds four new fields:
  - `failure_code` (e.g., `NO_TEMPLATE_AVAILABLE`, `MANUAL_PROVISION_REQUIRED`).
  - `failure_detail` (JSON payload describing missing template type, qiao_id, etc.).
  - `retry_count` (system-managed counter for operational visibility).
  - `last_retry_at` (timestamp of the last automated or manual retry attempt).
- `UNIQUE(from_qiao_id, to_qiao_id) WHERE status IN (1,8)` guarantees at most one pending/processing request per pair; duplicates now lock-and-retry instead of inserting new rows.
- A duplicate POST for the same `(from_qiao_id, to_qiao_id)` will reuse the existing pending row, increment `retry_count`, and attempt to finish the workflow again.

### 7. `square_character_entries`

```sql
CREATE TABLE square_character_entries (
    id SERIAL PRIMARY KEY,
    square_category VARCHAR(50) NOT NULL,
    qiao_id VARCHAR(32) NOT NULL,
    template_type_id INTEGER NOT NULL REFERENCES ai_template_types(id),
    entry_group VARCHAR(50) NOT NULL DEFAULT 'default',
    exposure_strategy VARCHAR(30) NOT NULL DEFAULT 'random',
    status INTEGER NOT NULL DEFAULT 1,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    last_featured_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(square_category, entry_group, qiao_id)
);
```

- Acts as a decoupled lookup for Square discovery; admin surfaces validate the `qiao_id`/profile relationship while the API drops any dangling configuration at read time.
- Random sampling is performed per category. Admins can pause exposure by setting `status=2` without touching the inventory tables.

## Data Flows

### 1. Admin: Provision Inventory

```
1. Create template type (`ai_template_types`).
2. Create character profile (`ai_personas`).
   - System generates `qiao_id`.
   - System upserts the `profiles` row (owner_type=2, owner_qiao_id matches the profile).
3. Optionally create multiple templates (`ai_templates`) under the same template type.
```

Notes:
- The number of character profiles can exceed the number of templates to deliver variety in Square while still constraining actual inventory.
- Manual characters (no template) still need a profile + template type to ensure inventory metadata is consistent.

### 2. User: Add AI Contact

```
1. User submits `POST /api/v1/contact-requests` with target `qiao_id`.
2. Contact service checks existing contacts/request rows for idempotency.
3. AI service loads the character profile by `qiao_id` -> obtains `template_type_id`.
4. Begin transaction:
   a. Lock the profile row (`FOR UPDATE`).
   b. Select a template with `FOR UPDATE SKIP LOCKED` (non-reusable first by priority, then reusable random/round-robin).
   c. Copy template configuration into a new `ai_instances` row and set `status=1`.
   d. Update `ai_templates.status=3` if `is_reusable=0`.
   e. Update `ai_personas.status=3` if `is_reusable=0`; always increment `usage_count`.
5. Commit transaction.
6. Create the contact row and emit CHAT_INFO for the applicant.
```

If step 4b finds **no template**, the service:
- Leaves the request in `status=PENDING`.
- Sets `failure_code='NO_TEMPLATE_AVAILABLE'`, `failure_detail={"template_type_id": X, "qiao_id": ...}`.
- Returns the standard success message to the user.

### 3. Template Shortage & Retry Workflow

```
1. Pending request with `failure_code` is surfaced in the admin “pending inventory” list.
2. Admin creates additional templates for the required template type.
3. Admin triggers a retry (from contacts view or admin dashboard).
4. System increments `retry_count`, updates `last_retry_at`, clears `failure_code`, and reruns the creation flow.
5. Success → ACCEPTED and contact created.
6. Failure again → re-populate `failure_code`/`failure_detail` with the fresh reason so admin sees up-to-date diagnostics.
```

The request ID never changes. Users attempting to re-add the same `qiao_id` route to the existing pending row and simply enqueue another retry.

## Template Selection Algorithm

```python
async def select_template(db: AsyncSession, template_type_id: int) -> Optional[AITemplate]:
    """Return a locked template row ready for consumption."""
    stmt = (
        select(AITemplate)
        .where(
            AITemplate.template_type_id == template_type_id,
            AITemplate.status == 1  # active only
        )
        .order_by(AITemplate.is_reusable.asc(), AITemplate.priority.asc(), AITemplate.id.asc())
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    return await db.scalar(stmt)
```

Usage guidelines:
- Always execute inside the same transaction that updates the template/profile/character rows.
- After creating the character, update `ai_templates.status` to 3 for single-use templates **before** committing.
- If the profile itself is single-use, also set its status to 3 before commit.

## Entity Relationships

```
ai_template_types (1) ──→ (N) ai_personas
ai_template_types (1) ──→ (N) ai_templates
ai_personas (1) ──→ (1) profiles (owner_qiao_id)
ai_personas (1) ──→ (N) ai_instances
ai_templates (1) ──→ (N) ai_characters (optional when admin creates manually)
users (1) ──→ (N) contacts
contacts (1) ──→ (1) ai_characters via qiao_id (for AI contacts)
square_character_entries (1) ──→ (1) qiao_id exposure entry
```

## Square Data Flow

1. Admin selects which `qiao_id` should appear in each Square category by inserting rows into `square_character_entries`. The UI/service validates `template_type_id` & profile existence before saving, and discovery APIs will drop any stale entry at read time.
2. Square API fetches entries by `square_category` and randomizes them client-side (optionally filtered by `metadata`).
3. Removing exposure is as simple as setting `status=2` for that entry; this does not affect the template inventory.

## Implementation Checklist

- [x] Rename `ai_template_categories` → `ai_template_types` in SQL and documentation.
- [x] Enforce `FOREIGN KEY` links (`ai_templates`, `ai_personas`, `ai_instances`).
- [x] Document status semantics (no `usage_status`).
- [x] Define transaction-safe template selection flow.
- [x] Add `square_character_entries` table.
- [x] Extend `contact_requests` with failure metadata.
- [x] Add `user_id`/`user_qiao_id` columns plus uniqueness constraint to `ai_instances`.
- [x] Add `template_type_id` to `square_character_entries` and enforce `qiao_id` validation via admin/service logic (no DB FK).
- [x] Add partial unique index on `contact_requests (from_qiao_id, to_qiao_id)` for statuses 1/8.
- [ ] Update SQLAlchemy models & CRUD (follow-up code task).
- [ ] Implement retry endpoint + admin tooling (documented separately in `docs/task/contact-request-retry.md`).
- [ ] Wire Square API to the new table.

## Admin & API Updates

### Discovery Management

- 新建 “Discovery” 分类，承载 `square_character_entries` 维护界面：字段包括 `square_category`、`qiao_id`、`template_type_id`、`entry_group`、`exposure_strategy`、`status`、`metadata`、`last_featured_at`。
- 支持新增/编辑/下架/批量导入曝光条目；metadata 允许输入 JSON（如标签、地域、曝光位信息）。
- 后台操作需实时验证 `qiao_id` 的 profile 是否存在且 `template_type_id` 匹配，否则拒绝保存。
- 数据接口：`GET /admin/discovery/entries`、`POST /admin/discovery/entries`、`PATCH /admin/discovery/entries/{id}`，均操作 `square_character_entries`，与模板库存完全解耦。

### Contact Request Pending View

- 后台列表根据 `(status=1 AND failure_code IS NOT NULL)` 展示挂起申请，字段：`request_id`、`from_qiao_id`、`to_qiao_id`、`template_type_id`、`failure_code`、`failure_detail`、`retry_count`、`last_retry_at`、`expires_at`。
- 列表操作含 “重试” 按钮，调用 `POST /api/v1/contact-requests/{id}/retry` 重置失败字段并重新执行实例化流程。
- contacts 视图也需加入相同的 “重试” 操作，确保客服或管理员能直接处理挂起记录。

### API Changes

- 新增 `POST /api/v1/contact-requests/{id}/retry`（需要 admin/系统权限），逻辑：
  1. 校验请求 `status=PENDING` 且未过期；
  2. 清空 `failure_code`、`failure_detail`，`retry_count += 1`，`last_retry_at = NOW()`；
  3. 异步执行模板选择 → 实例化 → 联系人创建。
- Square API 改为读取 `square_character_entries`：`GET /api/v1/discovery?category=love&count=...` 随机抽样并输出 qiao_id + metadata + template_type_id；返回前通过服务层过滤掉没有 profile 的条目，不再扫描模板或档案表。

## References

- `backend/database/init/01_schema.sql`
- `docs/development/contact-request-flow.md`
- `docs/task/contact-request-retry.md`
- `docs/prototype/database.md`


