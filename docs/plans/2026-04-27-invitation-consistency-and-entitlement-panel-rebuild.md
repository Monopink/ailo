# 邀请链路一致性修复与权益操作台重构方案

生效日期：2026-04-27

## 目标

- 完成邀请奖励规则读取、执行、统计三个链路的一致性治理，保证管理端与客户端展示口径一致。
- 完成邀请短链落地路径统一，保证短链与分享卡片进入同一小程序页面。
- 完成 Invitation Policy 卡片权限治理，`Viewer` 角色具备只读能力。
- 完成权益操作台重构，形成“独立页面 + `App Content` 入口 + 多权益类型通用操作”结构。
- 保持账本写入以统一服务为唯一入口，保证审计可追溯。

## 已确认决策

- 权益面板保持独立页面，菜单入口放在 `App Content` 分类。
- 权益操作台支持多权益类型通用操作。
- 邀请统计改为基于 `growth_reward_applies` 与 `user_entitlement_ledger` 真值计算。
- Invitation Policy 卡片对 `Viewer` 角色提供“可读不可写”能力。
- 邀请奖励规则采用单槽位唯一策略：每个 `target_role` 对应唯一全局生效规则。
- 统计真值采用双表口径：`growth_reward_applies` 主统计 + `ledger` 一致性校验。
- `GET /api/v1/invitations/stats` 使用新字段命名，不保留旧字段命名。
- 管理端权益幂等命中记录操作日志，日志显式携带 `applied` 状态。
- 迁移阶段若发现重复生效奖励规则，迁移直接失败并输出错误，阻断发布。

## 范围

### 包含

- 邀请策略读取链路、执行链路、统计链路的一致性修复。
- 邀请短链重定向路径统一。
- Invitation Policy 卡片权限与前端交互治理。
- 权益操作台页面、菜单分组、后端接口、审计日志结构重构。
- API/spec/plan 文档同步。

### 不包含

- 活动归因奖励模型重设计。
- 兑换码奖励模型重设计。
- 权益账本核心表结构重设计。

## 现状问题

1. Invitation Policy 读取逻辑按单条查询，奖励执行逻辑按规则列表执行，读取与执行口径不一致。
2. 邀请统计由“当前规则参数 × 绑定人数”推算，未使用奖励发放真值数据。
3. 邀请短链重定向路径与分享卡片路径不一致，存在入口分叉。
4. Invitation Policy 卡片接口读取与写入共用写权限校验，`Viewer` 无法读取卡片。
5. `entitlement-operations` 页面与最新设置页结构分离，入口分组与职责边界不符合当前后台结构。
6. 权益幂等命中场景写入日志但未标记 `applied`，审计语义不完整。

## 实施方案

### 1. 邀请奖励规则单槽位治理

- 修改数据与读取逻辑，固定以下两条规则槽位为唯一可用槽位：
  - `(trigger_event=1, target_role=2, scope_type=1, scope_id=0, entitlement_type=ai_contact_limit)`
  - `(trigger_event=1, target_role=3, scope_type=1, scope_id=0, entitlement_type=ai_contact_limit)`
- 新增迁移校验：若任一槽位存在多条 `status=active` 记录，迁移失败并抛出明确错误。
- `system_management` 与 `invitations` 统一复用同一规则解析函数，禁止各自实现规则选择逻辑。

### 2. 邀请统计真值口径改造（双表）

- `GET /api/v1/invitations/stats` 重构为双表真值统计：
  - 主统计源：`growth_reward_applies`（限定邀请人奖励槽位与权益类型）
  - 一致性校验源：`user_entitlement_ledger`（按 `ledger_id/idempotency_key/source_type` 对齐）
- 返回字段替换为新命名，按“规则参数 + 真值结果”分组输出：
  - `inviter_success_bind_count`
  - `inviter_rule_reward_contact_delta`
  - `inviter_rule_max_rewards_per_actor`
  - `inviter_reward_contact_limit_actual_total`
  - `inviter_reward_contact_limit_preview_total`
- 下线旧字段命名，不提供兼容返回。

### 3. 邀请入口路径统一

- 将短链重定向目标路径统一为 `/pages/boot/boot?inviteCode={code}`。
- 分享卡片路径与短链重定向共享同一常量定义，消除路径分叉。

### 4. Invitation Policy 卡片权限重构

- `GET /admin-api/system/invitation-policy` 对 `Viewer` 开放读取。
- `PUT /admin-api/system/invitation-policy` 保持 `Admin/SuperAdmin` 写权限。
- 页面渲染层输出 `can_write_invitation_policy`，前端据此处理只读态：
  - `Viewer` 可查看、可刷新。
  - `Viewer` 禁用保存按钮与写入请求。

### 5. 权益操作台重构（独立页面，挂载 App Content）

- 保留独立页面形态，路径继续使用 `/entitlement-operations`。
- 菜单位置调整到 `App Content` 分组；从 `Entitlement` 分组移除入口。
- 页面能力升级为通用多权益类型操作：
  - 权益类型：动态读取 `entitlement_types` 激活项。
  - 原因码：动态读取 `entitlement_reason_codes` 激活项。
  - 操作类型：保留 `grant/adjust`，作用于任意权益类型。
  - 最近操作列表：新增权益类型筛选与 `applied` 状态展示。
- 旧版临时页面文件迁入 `deleted/`，避免并行实现。

### 6. 权益操作审计语义补全

- `POST /admin-api/entitlements/operations` 在日志中记录统一结构：
  - `operation_desc` 包含 `operation_type/user_id/entitlement_type_code/delta/reason_code/applied/idempotency_key`
  - `resource_type` 细分为 `entitlement_operation`
- `applied=false` 场景照常记录日志，日志字段明确标记幂等命中。

### 7. 文档同步

- 更新 `docs/api/invitations.md`：统计字段、路径、口径定义。
- 更新 `docs/api/admin-entitlements.md`：多权益通用操作台行为与日志语义。
- 更新 `docs/spec/admin-panel/system-settings.md`：Invitation Policy 卡片权限行为。
- 新增或更新后台权益页面规范文档，明确入口归属 `App Content` 与页面能力边界。

## 实施步骤

1. 新增迁移：邀请奖励规则唯一槽位校验（重复生效规则即失败）。
2. 重构邀请规则读取函数，管理端与客户端统一调用。
3. 重构 `GET /api/v1/invitations/stats` 双表真值统计与字段结构。
4. 统一短链与分享卡片路径常量。
5. 调整 Invitation Policy 接口权限与页面只读态。
6. 重构权益操作台入口分组与页面能力（多权益类型通用）。
7. 补全权益操作日志 `applied` 语义。
8. 同步 API/spec/plans 文档。
9. 执行验证：`/validate`、关键接口联调、管理端手工回归。

## 验收标准

- Invitation Policy 读取结果与奖励执行结果使用同一规则槽位定义。
- 数据库中任一邀请奖励槽位出现重复生效规则时，迁移失败并阻断发布。
- `GET /api/v1/invitations/stats` 返回新字段命名，真值来源为 `growth_reward_applies + ledger`。
- 短链重定向与分享卡片路径一致，均为 `/pages/boot/boot?inviteCode={code}`。
- `Viewer` 可读取 Invitation Policy 卡片数据，写入操作被禁止。
- 权益操作台为独立页面，菜单归属 `App Content`，支持多权益类型通用操作。
- 权益幂等命中日志包含 `applied=false` 明确标记。
- 文档与实现一致，且仅描述当前有效状态。
