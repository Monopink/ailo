# P1-邀请码权益并发一致性与迁移清理

## 文档状态

- 状态：待实施
- 创建日期：`2026-05-10`
- 更新日期：`2026-05-10`
- 本文用途：记录邀请码/权益并发一致性收敛任务的实施输入与验收口径

## 背景状态

- 兑换码领取入口为 `POST /api/v1/redeem/claim`，实现位于 `backend/app/api/v1/growth.py` 的 `claim_redeem_code`。
- 领取链路使用“批次行锁 + 用户批次领取次数聚合查询 + claim 写入”的事务路径，语义一致性依赖批次级串行执行。
- 邀请码可绑定判定规则在 `backend/app/api/v1/invitations.py` 与 `backend/app/services/invitation/intake_orchestrator.py` 各有一份实现。
- 公网邀请码 intake 入口为 `POST /api/v1/public/invitations/intake`，存在客户端 IP 解析失败时的防护降级路径。
- 消息服务 LeanCloud 运行配置项迁移已落地：`backend/alembic/versions/20260510_01_remove_leancloud_message_runtime_configs.py`。

## 目标

1. 兑换码领取链路采用可扩展的原子配额模型，保持“每用户每批次上限”强一致。
2. 邀请码可绑定规则收敛为单一策略实现，消除规则分叉。
3. 公网邀请码 intake 入口采用 fail-closed 防护边界。
4. 相关计划文档与迁移现态保持一致。

## 实施范围

### 纳入范围

- 数据库：新增 `redeem_batch_user_counters` 表、历史数据回填迁移、约束与索引。
- 后端：兑换码领取写路径重构、邀请码可绑定规则收敛、公网 intake 防护收敛。
- 测试：并发一致性测试、计数一致性测试、安全边界测试。
- 文档：`docs/plans/*` 相关计划文档状态与口径对齐。

### 不纳入范围

- 邀请码页面交互改版。
- 权益类型字典重构。
- 消息服务 provider registry 功能改动。

## 实施内容

### 1. 兑换码原子配额模型落地

- 新增表 `redeem_batch_user_counters`：
  - 字段：`batch_id`、`user_id`、`claimed_total`、`created_at`、`updated_at`。
  - 约束：`UNIQUE(batch_id, user_id)`、`claimed_total >= 0`。
  - 索引：`(batch_id, user_id)` 唯一索引，`(user_id, updated_at)` 读侧索引。
- Alembic 迁移包含历史回填：从 `redeem_code_claims` 按 `(batch_id, user_id)` 聚合写入计数表。

### 2. 领取命令服务重构

- 将 `claim_redeem_code` 的写事务收敛到单一 service 命令。
- 事务流程：
  1. 锁定兑换码与批次记录。
  2. `UPSERT` 初始化 `(batch_id, user_id)` 计数行。
  3. 通过原子条件更新计数（`claimed_total < max_claims_per_user`）判定是否可领取。
  4. 写入 `redeem_code_claims`。
  5. 原子递增 `redeem_codes.claimed_total` 与 `redeem_code_batches.budget_used`。
  6. 执行奖励发放与账本写入。
- 保留现有幂等约束：
  - `uq_redeem_code_claims_user_code`
  - `uq_redeem_code_claims_idempotency_key`

### 3. 邀请码可绑定规则收敛

- 新增单一策略模块（domain policy），统一处理以下判定：
  - 邀请人存在且有效
  - 被邀请人未绑定
  - 非自绑
  - 非互绑闭环
- `invitations.py` 与 `intake_orchestrator.py` 统一调用该策略模块。

### 4. 公网 intake 防护边界收敛

- `public_invitations.py` 入口采用 fail-closed：
  - 客户端识别信息无法形成有效限流键时，直接拒绝请求。
  - 攻击扫描与封禁判定失败时返回保护性拒绝响应。
- 保持 `public_invite_intake` 速率限制配置组为唯一入口限流组。

### 5. 迁移清理现态对齐

- 将 LeanCloud 运行配置项迁移清理标记为已完成基线事项。
- 保持 `backend/database/bootstrap/base.sql`、`backend/database/bootstrap/env/*.sql` 与迁移口径一致。

## 验收标准

1. 并发压测下，同一用户在同一批次领取次数不超过 `max_claims_per_user`。
2. 成功领取后，`redeem_code_claims`、`redeem_codes.claimed_total`、`redeem_code_batches.budget_used`、`redeem_batch_user_counters.claimed_total` 计数一致。
3. 邀请码 resolve 与 bind 使用同一可绑定规则实现，行为一致。
4. 公网 intake 在识别键异常场景返回保护性拒绝，不进入放行路径。
5. 数据库中不存在 `leancloud_im_server_url`、`leancloud_im_service_conversation_id`、`leancloud_im_webhook_token`。

## 实施后验证

- 自动化测试：
  - 同用户同批次并发领取测试。
  - 领取成功后的四表计数一致性测试。
  - 公网 intake 识别键异常与攻击扫描异常测试。
- 迁移验证：
  - 执行 Alembic 升级后核对 `redeem_batch_user_counters` 回填结果。
  - 校验 `system_configs` 中三项 LeanCloud 运行配置项不存在。

## 已完成基线事项

- `2026-05-10`：`backend/alembic/versions/20260510_01_remove_leancloud_message_runtime_configs.py` 已落地。
