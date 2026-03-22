# 安全事件落库：attack_detected → user_violation_logs

## 范围

本方案仅覆盖：

1. `attack_detected=true` 时，标记触发该请求的用户消息为“排除上下文”（`is_excluded_from_context=1`）
2. `attack_detected=true` 时，写入一条 `user_violation_logs` 审计记录
3. 当 `user_violation_logs` 审计记录写入成功后，同步 best-effort 更新 `user_risk_stats` 汇总统计

本方案不覆盖：

- “占位符替换文本/配置字段”的设计（已明确不做）
- 任何基于 `user_violation_logs` 的自动处置联动（仅审计落库）
- `user_risk_stats.current_risk_level` 的自动升级/风控策略（仅汇总计数）

## 当前实现（已存在）

### 触发点（主链路）

`backend/app/services/ai/orchestrators/llm_response_handler.py`

- 当 `ai_response.attack_detected=true` 且存在 `user_message_item_id`：
  - 调用 `mark_conversation_item_as_excluded(db, user_message_item_id)`
  - 当前未写入 `user_violation_logs`

### 上下文构建行为

`backend/app/services/ai/queries/conversation_queries.py:get_conversation_contexts`

- 构建 prompt 的上下文查询仅取 `is_excluded_from_context = INCLUDED(0)` 的消息
- 因此被标记排除的消息不会进入后续 prompt

## 目标结果（本次落地）

当 `attack_detected=true` 且 `user_message_item_id` 存在时：

1. 仍执行“排除上下文”标记：
   - 目标：`ai_conversation_items.is_excluded_from_context = 1`
   - 失败策略：best-effort；失败仅记录 ERROR 日志，不中断消息流程
2. 新增写入 `user_violation_logs`：
   - 目标：插入一条 `UserViolationLog` 记录
   - 失败策略：best-effort；失败仅记录 ERROR 日志，不中断消息流程
   - 重复策略：允许重复记录（不做幂等约束）
3. 同步更新 `user_risk_stats`：
   - 目标：更新用户风险汇总统计（计数与最后时间）
   - 失败策略：best-effort；失败仅记录 ERROR 日志，不中断消息流程
   - 统计口径：包含所有检测记录（PENDING + CONFIRMED）
   - 重复策略：允许重复计数

## 业务决策（已拍板）

### 1) 关联范围

- 排除上下文仅针对“触发该请求的用户消息记录（单条）”

### 2) user_violation_logs 字段固定取值

- `violation_type`: `ViolationType.PROMPT_INJECTION (1)`
- `severity_level`: `SeverityLevel.LOW (1)`
- `auto_action_taken`: `AutoAction.NONE (1)`
- `manual_review_status`: `ManualReviewStatus.PENDING (1)`

### 3) original_message 取值规则

- 当消息为 text：写入原始 `text_content`
- 当消息为非 text（image/audio）：写入固定占位文本：`[Non-text message]`

### 4) 不新增配置

- 不新增任何 `system_configs` 配置键
- 不新增任何“占位符替换文本”的 prompt 逻辑

### 5) user_risk_stats 更新规则（汇总计数）

- 写入时机：`user_violation_logs` 插入成功后立即更新
- 统计口径：包含所有检测记录（PENDING + CONFIRMED）
- 重复策略：允许重复计数
- 不变更字段：`current_risk_level`、`warning_count`、`restriction_count`、`suspension_count`、`last_action_at`
- 更新字段：
  - `total_violations += 1`
  - `violation_by_type[<type_key>] += 1`
  - `last_violation_at = now()`
  - `consecutive_violations`：若距离上次违规 > 7 天则置 1，否则 +1

## 技术方案（实现要点）

### A. 新增落库写入点

实现位置：

- `backend/app/services/ai/orchestrators/llm_response_handler.py`

行为：

- 在 `attack_detected` 分支内：
  1) 调用 `mark_conversation_item_as_excluded(db, user_message_item_id)` 并检查返回值
     - 返回 `False` 时记录 ERROR 日志
  2) best-effort 插入 `UserViolationLog`

### B. user_id / instance_id 来源

- `user_id`: 通过 `user_qiao_id` 查询得到（`get_user_id_by_qiao_id`）
- `instance_id`: 使用 `instance_context["instance_id"]`

### C. original_message 来源

- 从 `ai_conversation_items` 读取 `user_message_item_id` 对应记录：
  - `message_type == "text"`：取 `text_content`
  - `message_type != "text"`：写入固定占位文本
- 当记录不存在或读取失败：写入固定占位文本

### D. 事务与错误处理边界

- `mark_conversation_item_as_excluded`：best-effort
- `user_violation_logs` 写入：best-effort
- `user_risk_stats` 更新：best-effort
- 两者失败均不影响后续消息流程，仅记录 ERROR 日志

## 验证标准（验收）

1. 当 `attack_detected=true` 时：
   - 触发消息行的 `is_excluded_from_context` 被置为 1（若写入成功）
   - `user_violation_logs` 新增 1 条记录（若写入成功）
   - `user_risk_stats` 对应用户汇总计数更新（若写入成功）
2. 当排除标记写入失败或 `user_violation_logs` 写入失败时：
   - 不中断消息流程
   - 必须记录 ERROR 日志
3. `user_violation_logs` 字段满足“业务决策”中的固定取值与 `original_message` 规则

## 需同步修正的规范文档（与拍板一致）

1. `docs/spec/ai/prompt-building.md`
   - 将“更新该 buffer 关联的所有用户消息”调整为“更新触发该请求的用户消息记录（单条）”
2. `docs/spec/ai/llm-interaction.md` 与 `docs/spec/ai/conversation-flow.md`
   - 将 `attack_detected` 的排除标记失败边界调整为 best-effort（失败仅记录 ERROR，不中断消息流程）
