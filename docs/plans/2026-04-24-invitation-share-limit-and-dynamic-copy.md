# 邀请分享页上限与动态文案实施方案（2026-04-24）

## 1. 任务范围

本次实施仅包含以下内容：

1. 邀请码绑定链路增加“邀请人数上限”硬限制。
2. 邀请分享页文案与统计改为读取后端动态返回。
3. 同步更新邀请相关 API 契约与客户端运行时校验。

## 2. 固定决策

1. “最多邀请 X 人”语义定义为：单个邀请人可成功邀请并完成绑定的 invitee 数量上限（硬限制）。
2. 邀请上限来源使用现有奖励规则 `growth_reward_rules.max_rewards_per_actor`（邀请人规则）。
3. 联系人奖励相关展示值由后端返回，前端不自行推导核心业务口径。
4. 当邀请上限为 `null` 时，前端隐藏“最多邀请 X 人”相关文案。
5. 页面文案展示统一由接口返回字段驱动。

## 3. 已确认问题

1. `invite-share` 页面存在多处固定 `+1` 文案，未与后端配置联动。
2. 现有 `GET /api/v1/invitations/stats` 仅返回 `success_invite_count`，不足以支撑动态文案。
3. 现有 `POST /api/v1/invitations/bind` 未执行“邀请人数上限”拦截，当前仅限制奖励发放次数，不限制邀请关系增长。

## 4. 目标行为

### 4.1 绑定行为

1. 绑定邀请码时，服务端按 inviter 当前成功邀请人数与 `max_invite_count` 比较。
2. 当 `max_invite_count` 为非空且已达上限时，拒绝绑定并返回 `400`。
3. 错误文案统一为：`邀请人数已达上限`。
4. 当 `max_invite_count` 为 `null` 时，不限制邀请人数。

### 4.2 邀请统计与展示行为

`GET /api/v1/invitations/stats` 返回以下字段：

1. `success_invite_count`：当前用户邀请成功人数。
2. `max_invite_count`：邀请人数上限（`integer | null`）。
3. `reward_contact_limit_per_invite`：每次邀请成功可获得的联系人上限增量。
4. `max_reward_contact_limit_total`：可获得联系人上限总增量（`max_invite_count * reward_contact_limit_per_invite`，当上限为 `null` 时返回 `null`）。
5. `rewarded_contact_limit_total`：当前已获得的联系人上限总增量。

## 5. 实施方案

### 5.1 后端

1. 扩展 `InvitationStatsResponse` schema，加入新增统计字段。
2. 在邀请模块中新增“邀请规则读取”逻辑：
   - 读取当前生效的 inviter 奖励规则（`trigger_event=INVITEE_SETUP_COMPLETED`，`target_role=INVITER`，`entitlement=ai_contact_limit`）。
   - 获取 `delta_granted` 作为 `reward_contact_limit_per_invite`。
   - 获取 `max_rewards_per_actor` 作为 `max_invite_count`。
3. 在 `POST /api/v1/invitations/bind` 中落地上限校验：
   - 在现有事务与用户锁范围内，按 inviter 统计已邀请成功人数；
   - 若达到 `max_invite_count`，返回 `400` 与固定错误文案。
4. 在 `GET /api/v1/invitations/stats` 内统一计算并返回总增量字段。

### 5.2 小程序

1. 更新 `InvitationStatsResponseSchema` 与类型定义。
2. `invite-share` 页面改为基于新增字段渲染：
   - 所有 `+1`、`各增加 1 个联系人上限` 文案改为动态值；
   - “最多邀请 X 人”文案仅在 `max_invite_count !== null` 时显示；
   - “已增加联系人上限”显示 `rewarded_contact_limit_total`。
3. 清理页面中的固定奖励数字，保持单一数据源为 `stats` 接口返回。

### 5.3 文档

1. 更新 `docs/api/invitations.md`：
   - 补充 `GET /api/v1/invitations/stats` 新字段；
   - 补充 `POST /api/v1/invitations/bind` 新增 `400` 错误语义 `邀请人数已达上限`。
2. 更新相关 `docs/spec/client/base/*` 页面行为描述，使邀请分享页文案口径与接口字段一致。

## 6. 验收标准

1. 当 inviter 已达到上限时，新的 invitee 绑定返回 `400`，错误文案为 `邀请人数已达上限`。
2. `GET /api/v1/invitations/stats` 返回新增字段且字段值与当前生效规则一致。
3. `invite-share` 页面不出现固定 `+1` 业务文案。
4. 当 `max_invite_count=null` 时，页面不展示“最多邀请 X 人”文案。
5. 前后端类型校验、运行时校验与项目验证流程通过。

## 7. 实施结果

待实施。
