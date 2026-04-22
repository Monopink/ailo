# 动态 AI 联系人上限 + 邀请活动体系（实施方案）

## 背景

- 目标是将 AI 联系人能力统一到权益账户模型，并通过“用户邀请 + 活动邀请码”两类链路发奖。
- 不保留旧口径与兼容层，邀请统计事件统一为 `open` 识别口径。

## 目标

- 仅限制 **AI 联系人数量**（`contacts.contact_type = AI`）。
- 上限接口返回 `used + available_total`（可新增槽位），不再返回历史 `limit(granted_total)` 语义。
- 用户邀请码固定 6 位字母数字；解析/绑定具备限频控制。
- 支持“活动实体 + 多邀请码”：
  - 活动承载奖励策略和生命周期；
  - 同一活动可挂多个邀请码（二维码/渠道统计）。
- 口令模板由后端动态下发，前端复制到剪贴板后可外部粘贴发送。

## 数据模型

- `invite_campaigns`
  - 活动实体：`name`、`status`、`starts_at`、`ends_at`、`max_bindings`
- `invite_campaign_reward_rules`
  - 奖励规则实体：`code_type`、`campaign_id`、`target_role`、`trigger_event`
  - 权益映射：`entitlement_type_id`、`delta_granted`
  - 限制与调度：`max_rewards_per_actor`、`priority`、`status`
- `invite_codes`
  - 全局唯一 `code`
  - `code_type`: `1=user` / `2=campaign`
  - `owner_user_id`（仅 user code）
  - `campaign_id`（仅 campaign code）
  - `status`
- `invite_bindings`
  - `invitee_user_id`（唯一）
  - `invite_code_id`
  - `code_type` / `code_snapshot` / `inviter_user_id_snapshot`
- `invite_events`
  - 事件类型：`open`、`resolve_valid`、`bind_success`、`setup_completed`、`copy_command`、`share_wechat`
  - 统计维度：`invite_code_id + event_type + created_at`
- `user_entitlement_accounts` + `user_entitlement_ledger`
  - `ai_contact_limit` 以账户可用值 `available_total` 为读口径
  - 新增/删除 AI 联系人分别写 `consume`/`refund`

## 规则

- 互斥：用户最多绑定一次邀请码（每人最多被邀请一次）。
- 用户邀请码：
  - invitee：绑定成功 `+1`；
  - inviter：仅前 3 次成功邀请各 `+1`；
  - 反向约束：用户不可填写“自己邀请过的人”的邀请码。
- 活动邀请码：
  - 仅允许 `users.needs_profile_setup=true` 时绑定；
  - 奖励按活动规则配置（`code_type=campaign`）；
  - 生命周期校验：`status + starts_at + ends_at + max_bindings`。

## API

- `GET /api/v1/invitations/code`
- `GET /api/v1/invitations/command`
- `POST /api/v1/invitations/resolve`
- `POST /api/v1/invitations/bind`
- `POST /api/v1/invitations/events`
- `GET /api/v1/contacts/ai-limit`

## 小程序入口

- setup 页面：
  - 可选填写邀请码；
  - 支持剪贴板口令自动预填；
  - 支持链接参数 `inviteCode` 自动预填。
- setup 后拆分为两个页面：
  - 邀请码填写页（resolve/bind）；
  - 邀请分享页（查看我的邀请码、复制口令、微信分享）。

## 迁移与初始化

- 新用户创建时通过权益服务写入 `system_initial`。
- 联系人新增写 `consume`，联系人删除写 `refund`。
- 开发环境按“单一迁移链”重建；不叠加历史过渡迁移。

## 验收点

- 邀请码全局唯一，无跨类型冲突。
- 用户码 setup 后仍可绑定；活动码 setup 后不可绑定。
- 邀请事件口径无 `page_view` 残留，`open` 可用。
- 联系人并发新增不突破 `available_total`。
