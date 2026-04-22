# 邀请码与权益系统加固实施计划（2026-04-21）

## 1. 任务范围

本次实施仅包含以下已确定内容：

1. 新增匿名邀请码 `open` 埋点接口：`POST /api/v1/public/invitations/open`。
2. 修复“用户已完成 setup 后再绑定邀请码”场景下 inviter 奖励漏发问题。
3. 将奖励限次统计从 `user_entitlement_ledger.event_payload` JSON 提取切换为结构化记录。
4. 删除绑定接口响应中的冗余字段 `inviter_reward_contact_limit`，并同步前后端契约。
5. 同步更新文档与迁移定义。

## 2. 约束

1. 不保留兼容层，不引入临时过渡方案。
2. 数据库变更通过模型与 Alembic 迁移落地。
3. `backend/alembic/versions/*.py` 与模型定义保持一致。
4. 文档仅描述最终行为与约束，不记录实现过程细节。

## 3. 接口调整

### 3.1 新增匿名 open 埋点接口

- 路径：`POST /api/v1/public/invitations/open`
- 认证：无需登录
- 行为：仅写入 `invite_events` 的 `open` 事件，不返回邀请码有效性判断结果
- 输入：`code`、`source`、`trigger`、`payload?`
- 输出：`accepted=true`

### 3.2 邀请码绑定接口响应精简

- 路径：`POST /api/v1/invitations/bind`
- 删除字段：`inviter_reward_contact_limit`
- 保留字段：`code_type`、`reward_contact_limit`

## 4. 数据模型调整

新增结构化奖励应用记录表：`growth_reward_applies`。

用途：

1. 作为奖励规则命中与已发放事实记录。
2. 作为 `max_rewards_per_actor` 的统计来源。
3. 避免在账本 JSON 字段上执行规则统计。

核心字段：

- `rule_id`
- `trigger_event`
- `target_role`
- `actor_user_id`
- `beneficiary_user_id`
- `source_type`
- `source_id`
- `scope_type`
- `scope_id`
- `entitlement_type_id`
- `delta_granted`
- `ledger_id`
- `idempotency_key`
- `event_payload`
- `created_at`

关键约束与索引：

1. `UNIQUE(idempotency_key)`
2. `UNIQUE(ledger_id)`
3. 索引 `(rule_id, actor_user_id, created_at)`
4. 索引 `(source_type, source_id)`

## 5. 服务逻辑调整

1. `apply_growth_rewards` 按规则循环执行时，奖励限次统计改查 `growth_reward_applies`。
2. 奖励发放成功后在同事务写入 `growth_reward_applies`。
3. 邀请码绑定成功后：
   - 始终触发 invitee 奖励（现有行为）。
   - 若 invitee 当前已完成 setup，则立即补触发 inviter 奖励。

## 6. 实施顺序

1. 更新 `docs/api` 与 `docs/spec` 契约文档。
2. 更新模型与 Alembic 迁移。
3. 更新 CRUD/Service/API。
4. 更新小程序调用与运行时 schema。
5. 执行迁移链路验证。
6. 执行验证并修复问题。

## 7. 验收标准

1. 未登录状态可成功上报邀请码 `open` 事件。
2. 已 setup 用户绑定邀请码后，inviter 奖励可立即发放且幂等。
3. 奖励限次不再依赖账本 JSON 检索。
4. 绑定接口响应不再包含 `inviter_reward_contact_limit`。
5. `backend/alembic/versions/*.py` 与模型一致。
6. 后端与前端校验流程通过。
