# 邀请码与权益系统重构实施方案（2026-04-17）

## 1. 目标与范围

本次实施重构邀请码/权益相关系统，采用无历史包袱的干净落地方式，不保留兼容层，不保留旧架构冗余路径。

范围包括：

- 后端领域模型、枚举、CRUD、服务、API
- Alembic 迁移与数据库初始化产物
- `docs/spec/*`、`docs/api/*`、`docs/data-dict/*` 对齐
- 小程序 setup 与邀请码链路对齐

## 2. 固定决策

- 邀请码仅用于用户邀请关系，不承载官方活动。
- 官方奖励通过兑换码发放。
- 邀请奖励与上限全部动态配置，后台可视化修改。
- 奖励可叠加（邀请 + 活动归因 + 兑换码）。
- 同一次奖励执行采用单事务：全成功或全回滚。
- 管理员手工发放可突破普通用户累计上限，并保留审计。
- 活动归因采用首次归因（first-touch）。
- 活动归因奖励每用户最多 1 次。
- 新用户奖励窗口基于注册时间计算。
- 邀请人默认上限 3 次，配置可改。
- 用户邀请码固定为 6 位大写字母数字。
- 兑换码同时支持一次性码和批次通用码。
- 兑换码支持生效/失效时间窗。
- 兑换码批次支持预算上限。

## 3. 最终架构

### 3.1 邀请域（Invitation）

- 仅保留用户邀请码与邀请绑定。
- 不包含活动字段、不包含奖励规则字段。

### 3.2 活动归因域（Attribution）

- 通过隐式上报记录活动归因，不通过邀请码输入。
- 每用户首个有效归因生效并锁定。

### 3.3 兑换码域（Redeem）

- 提供兑换码批次、兑换码、兑换记录。
- 支持批次预算、时间窗、一次性码/通用码。

### 3.4 奖励执行域（Reward Engine）

- 统一规则表驱动邀请、归因、兑换奖励发放。
- 奖励落账统一写入权益账本（`user_entitlement_ledger`）。

## 4. 数据模型（目标态）

### 4.1 保留并重定义

- `invite_codes`
  - `code`（6位大写字母数字，全局唯一）
  - `owner_user_id`（唯一）
  - `status`
- `invite_bindings`
  - `invitee_user_id`（唯一）
  - `invite_code_id`
  - `inviter_user_id_snapshot`
  - `code_snapshot`

### 4.2 新增

- `campaigns`：活动主数据（用于归因）
- `campaign_attributions`：首次归因记录（`user_id` 唯一）
- `redeem_code_batches`：兑换码批次与预算
- `redeem_codes`：具体兑换码（一次性/通用）
- `redeem_code_claims`：兑换领取记录（含幂等与审计）
- `growth_reward_rules`：统一奖励规则（邀请/归因/兑换）

### 4.3 移除

- `invite_campaigns`
- `invite_campaign_reward_rules`
- `invite_codes` 中与奖励耦合字段（`reward_contact_limit`、`inviter_reward_contact_limit`、`inviter_reward_cap`）

## 5. API（目标态）

### 5.1 邀请码 API（仅用户邀请码）

- `GET /api/v1/invitations/code`
- `GET /api/v1/invitations/command`
- `POST /api/v1/invitations/resolve`
- `POST /api/v1/invitations/bind`

### 5.2 活动归因 API（隐式）

- `POST /api/v1/growth/attributions/track`

### 5.3 兑换码 API

- `POST /api/v1/redeem-codes/claim`

## 6. 奖励规则执行

统一由奖励执行器按 `growth_reward_rules` 处理：

- 触发源：
  - `invite_bind_success`（目标：invitee）
  - `invitee_setup_completed`（目标：inviter）
  - `campaign_attribution_first_touch`（目标：actor）
  - `redeem_code_claim_success`（目标：actor）
- 支持：
  - 每规则每用户限次
  - 新用户窗口累计上限
  - 管理员发放越权标记
  - 幂等去重

## 7. 前端目标行为

- setup 页仅展示“用户邀请码（可选）”输入语义。
- 活动归因不通过邀请码输入，改为隐式链路上报。
- 邀请码自动预填仅接受用户邀请码并做服务端可绑定校验。
- 兑换码通过独立入口调用兑换 API。

## 8. 迁移与落地策略

- 由于 prod 未部署旧改动，本次直接重写对应迁移至目标态。
- 开发环境允许重建数据库，确保无过渡链条。
- 迁移后生成并同步：
  - `backend/database/init/sql/01_schema.sql`
  - `docs/data-dict/schema.*.tsv`

## 9. 实施顺序

1. 更新 `docs/api`、`docs/spec` 到目标口径。
2. 重构后端模型、枚举、CRUD、服务、路由。
3. 重写 Alembic 迁移并执行 schema 产物生成。
4. 对齐小程序 setup 与邀请码流程。
5. 执行后端/前端验证并修复。
6. 回填本方案文档实施结果。

## 10. 验收标准

- 代码与文档中不再存在“活动邀请码填写/绑定”语义。
- 邀请码仅保留用户邀请关系语义。
- 兑换码可按批次预算、时间窗、模式（一次性/通用）生效。
- 奖励规则可配置、可叠加、可追溯。
- 奖励执行单事务全成功/全回滚。
- 活动归因采用首次归因且每用户最多一次奖励。
- schema 与 data-dict 与模型一致，无残留旧字段定义。
- 校验流程通过，无跳过失败项。

## 11. 实施结果

- 已完成 `docs/api/invitations.md` 与 `docs/spec/client/base/profile-setup.md` 对齐，邀请码语义仅保留用户邀请码，活动归因改为隐式上报。
- 已完成后端领域重构：
  - 邀请域：`invite_codes` / `invite_bindings` / `invite_events`（仅用户邀请码语义）。
  - 活动归因域：`campaigns` / `campaign_attributions`。
  - 兑换码域：`redeem_code_batches` / `redeem_codes` / `redeem_code_claims`。
  - 奖励规则域：`growth_reward_rules`（统一驱动邀请/归因/兑换奖励）。
- 已完成 API 重构：
  - 邀请码接口仅处理用户邀请码。
  - 新增活动归因接口 `POST /api/v1/growth/attributions/track`。
  - 新增兑换接口 `POST /api/v1/redeem-codes/claim`。
- 已完成奖励执行器改造：
  - 邀请人奖励在 invitee setup 完成时触发。
  - 邀请奖励、归因奖励、兑换奖励可叠加。
  - 新用户窗口累计上限使用系统配置 `growth_new_user_reward_window_days`、`growth_new_user_reward_cap_total`。
- 已完成迁移与数据库产物对齐：
  - 重写 `20260412_00_add_invitations_and_entitlements.py` 为目标态迁移。
  - 同步 `backend/database/init/sql/01_schema.sql`。
  - 同步 `docs/data-dict/schema.tables.tsv`、`schema.columns.tsv`、`schema.constraints.tsv`。
  - 同步 `backend/database/init/sql/02_required_data*.sql` 的默认奖励规则与新增配置键。
- 已完成小程序链路对齐：
  - setup 仅处理用户邀请码输入。
  - 活动参数改为隐式归因上报。
  - 登录到 setup 的 `campaignCode` 透传与解析链路打通。
- 验证结果：
  - 后端：`ruff format --check`、`ruff check`、`mypy`、`lint-imports` 全通过。
  - 前端：`npm run check` 全通过。
  - 数据库：开发库重建后执行 `alembic upgrade head` 成功，schema 产物成功生成。
