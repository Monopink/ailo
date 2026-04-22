# 权益账本与账户模型重构（实施计划）

## 背景

现有 `user_entitlement_batches` 仅支持按批次累加，读路径依赖聚合计算，不具备标准化的账本动作语义，也缺少账户读模型。该结构无法作为后续“邀请码、活动赠送、订阅购买”等多来源权益体系的统一底座。

## 目标

- 废弃 `user_entitlement_batches`，切换为账本+账户模型。
- 引入权益类型字典，统一跨业务来源。
- 引入原因码字典，支撑管理员手工发放/调整场景。
- 读路径从实时聚合切换到账户表读取。
- 邀请码奖励发放改为写账本并更新账户。
- 新用户初始权益改为写账本并更新账户。
- 管理后台提供“权益操作台”，统一调用 service，不允许直接表级修改。
- 移除 `Invite Codes` 列表中的旧浏览口径字段，统一为 `open` 识别口径。

## 数据模型（最终态）

### entitlement_types

- `id` (PK)
- `code` (唯一，例：`ai_contact_limit`)
- `mode` (`1=capacity`, `2=consumable`)
- `unit` (例：`count`)
- `status` (`1=active`, `2=inactive`)
- `created_at` / `updated_at`

### user_entitlement_accounts

- `id` (PK)
- `user_id` (FK users)
- `entitlement_type_id` (FK entitlement_types)
- `granted_total` (累计授予)
- `used_total` (累计消耗)
- `available_total` (可用值)
- `version` (并发控制)
- `created_at` / `updated_at`
- 约束：`(user_id, entitlement_type_id)` 唯一；`granted_total>=0`、`used_total>=0`、`available_total>=0`、`available_total=granted_total-used_total`

### user_entitlement_ledger

- `id` (PK)
- `user_id` (FK users)
- `entitlement_type_id` (FK entitlement_types)
- `action_type` (`1=grant`, `2=consume`, `3=refund`, `4=adjust`)
- `delta_granted` (可正可负)
- `delta_used` (可正可负)
- `source_type`（枚举约束：`system_initial`、`invite_bind_invitee`、`invite_bind_inviter`、`contact_ai_slot`、`admin_manual_grant`、`admin_manual_adjust`）
- `source_id` (业务引用ID)
- `reason_code` (FK entitlement_reason_codes.code, 可空)
- `operator_admin_user_id` (FK admin_users.id, 可空)
- `idempotency_key` (幂等键)
- `effective_at`
- `event_payload` (JSON)
- `created_at`
- 约束：`(user_id, entitlement_type_id, idempotency_key)` 唯一；`delta_granted != 0 OR delta_used != 0`

### entitlement_reason_codes

- `id` (PK)
- `code` (唯一，例：`admin_activity_reward`)
- `display_name`
- `description` (可空)
- `is_system` (bool)
- `status` (`1=active`, `2=inactive`)
- `created_at` / `updated_at`

## 实施范围

### 包含

- `backend/app/models/entitlement.py` 重构为类型/来源/原因码/账户/账本模型。
- 重写 `20260412_00_add_invitations_and_entitlements.py`，直接创建邀请码+权益目标表结构与字典种子。
- `backend/app/crud/entitlement.py` 重构为类型/来源/原因码/账户/账本 CRUD。
- `backend/app/services/entitlement/service.py` 重构为“写账本+更新账户”的统一入口。
- `backend/app/api/v1/invitations.py` 改为调用新权益服务发放奖励。
- 新增 `backend/app/api/admin/entitlements.py` 管理员权益操作 API（grant/adjust）。
- 新增后台 `EntitlementOperationView` 操作台页面。
- `backend/app/api/v1/auth.py`、`backend/app/admin/views/user_views.py` 继续通过 `ensure_system_initial_ai_contact_limit` 初始化。
- `backend/app/services/contact/request_service.py` 与 `backend/app/api/v1/contacts.py` 保持读取 `get_ai_contact_limit`。
- Admin Growth 视图包含 `EntitlementReasonCode`、`UserEntitlementAccount`、`UserEntitlementLedger` 与 `Entitlement Operations`。
- `backend/database/init/sql/01_schema.sql` 与 `docs/data-dict/*` 生成同步。

### 不包含

- 订阅业务表（`subscription_plans` / `user_subscriptions`）与配额消费流水（`usage_events`）在本次不落地。
- 前端邀请页面交互改动不纳入本次主任务。

## 迁移策略（基线化）

1. 迁移链重排为两条：
   - `20260411_01`：`baseline`（空迁移，`down_revision=None`）
   - `20260412_00`：邀请码+权益目标态迁移（保留）
2. 历史迁移脚本全部归档到 `deleted/backend/alembic/versions/`，不再参与链路。
3. 在 `20260412_00` 中直接创建 `entitlement_types`、`entitlement_reason_codes`、`user_entitlement_accounts`、`user_entitlement_ledger` 并写入字典种子。
4. `20260412_00` 采用增量对齐：对基线中的 `invite_*` 与权益账本相关表做结构对齐，并新增 growth/redeem 相关表。
5. 不保留中间态迁移逻辑；不引入过渡兼容层。
6. 开发库采用 SQL 重建后 `stamp/upgrade` 到 head；生产库按 baseline 后执行 `20260412_00`。

说明：生产未执行邀请码迁移，且无需保留历史迁移链，故采用基线化以降低后续维护成本。

## 服务层规则

- 所有权益发放必须调用统一接口：
  - 先插入账本（幂等）
  - 再锁账户行并更新 `granted_total/available_total/version`
- `get_ai_contact_limit` 从 `user_entitlement_accounts` 读取。
- `ensure_system_initial_ai_contact_limit` 使用固定幂等键 `system_initial:0`。
- 管理员手工操作仅允许调用统一 service，操作类型为 `grant/adjust`。
- 账本写入强制校验 `source_type` 枚举与 `reason_code` 字典有效性。

## 验收标准

- 代码中不再引用 `user_entitlement_batches` 模型/CRUD。
- 邀请码绑定后仍正确发放 AI 联系人上限奖励。
- 新用户创建仍正确写入初始上限。
- 管理员可通过后台操作台调用 API 执行 `grant/adjust`，并写入 `user_entitlement_ledger` + `user_entitlement_accounts`。
- `Invite Codes` 列表不再展示旧浏览口径字段。
- `GET /contacts/ai-limit` 返回值正确。
- Alembic 升级可通过，`01_schema.sql` 与 `docs/data-dict/*` 同步。

## 实施记录（2026-04-16）

- 已落地 `entitlement_reason_codes`、`user_entitlement_accounts`、`user_entitlement_ledger`，并在迁移中写入字典种子。
- 已新增管理员权益操作能力：
  - API：`POST /admin-api/entitlements/operations`
  - 后台：`Entitlement Operations` 自定义页面 + Growth 区字典与账本视图
- 已移除后台 Invite Codes 列表中的旧浏览口径展示，仅保留 `resolve_valid/bind_success/setup_completed` 统计。
- 已完成开发库重建与迁移验证：
  - SQL 初始化脚本可执行；
  - Alembic 版本达到 `20260412_00`；
  - 重新生成 `01_schema.sql` 与 `docs/data-dict/schema.*.tsv` 并与模型对齐。
- 为兼容基线初始化顺序，`02_required_data*.sql` 的权益字典 seed 已改为“表存在时插入”。
- 已将 `20260411_01` 升级为“完整可建库基线迁移”（固定 SQL 快照），支持从空库直接 `alembic upgrade head`。
