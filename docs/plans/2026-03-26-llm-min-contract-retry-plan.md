# 2026-03-26 最小契约重试 + 消息优先 + 分级校验方案

## 已确认决策

- 响应字段分级：
  - L0（硬门槛）：`attack_detected`、`should_block`、`should_reply`、消息数组字段必须满足最小契约，否则本次 attempt 失败并进入重试。
  - L1（可选项）：`score`、`memory_operations` 等字段校验不通过时整项丢弃，不影响消息发送。
- 校验闸门分层：
  - 运行时硬闸门仅做 L0 最小契约（L0-only gate）。
  - L1 字段不参与运行时硬闸门，由编排层手工校验并裁剪。
- Schema 使用（请求侧保持现状不变）：
  - 调用 LLM 时仍传递完整运行时 schema（用于结构化输出约束/引导，尽量保证“最好情况直接可用”）。
  - 若 Provider/SDK 因 schema 约束导致请求失败或超时，视为本次 attempt 失败并进入重试。
  - 运行时不得使用“整包 schema 校验”作为硬闸门；L1 仅手工校验并裁剪。
- `outgoing_messages` / `followup_messages`：
  - 仅允许数组类型，元素必须为**非空字符串**；出现空字符串或非字符串元素视为结构错误（L0 失败）。
  - `should_reply=false` 时允许消息字段为空或缺失。
  - `should_reply=true` 且仅 `followup_messages` 非空：不发送 `outgoing_messages`，按正常流程仅发送 `followup_messages`（含延迟）。
- 重试：
  - 覆盖：JSON 解析失败、L0 契约失败、LLM 传输失败/超时等“无法得到可用 L0”的情况。
  - attempt 上限默认 3 次；由 `system_config` 控制。
  - 任意时刻检测到抢占（新消息优先）后立即停止且不再重试。
- 失败对用户侧表现：静默失败（不发送 `CHAT_INFO`，不触发 `mark_message_failed` 客户端动作）。
- 失败标记：必须落库（以 `ai_request_logs` 为主，最小闭环）。
- attempt 日志写入入口保持唯一：由 `conversation_flow` 统一写 `ai_request_logs`；`llm_response_handler` 不再写日志。
- buffer 终态：失败与成功均 finalize 为 `COMPLETE`；仅抢占/中断使用 `CANCELLED`。
- `should_reply` 仅作为“是否回复”的确认，不影响其他字段处理（`score` / `memory` 仍按规则处理）。
- 纠错提示（correction prompt）：暂不启用；预留设计另见 `docs/plans/issues/P3-llm-min-contract-retry-correction-prompt.md`。

## 背景与问题

- 当前链路将运行时 JSON Schema 校验作为整包硬闸门：任一字段校验失败会导致整次请求失败，从而阻断消息发送。
- 结构化输出在 Provider 侧存在不稳定性：可能出现结构满足但数值越界等情况（例如 `score` 维度为负数）。
- 需求变更目标：在保证安全字段与消息字段可靠的前提下，尽可能保证消息可用；其余字段尽力处理，失败即丢弃，不扩大失败面。

## 术语

- attempt：一次 LLM 调用与解析/校验/落库/发送的完整流程；重试会产生多个 attempt。
- L0 最小契约：满足“安全副作用 + 消息可发送”的最低字段集合与严格类型约束。
- L1 可选字段：不影响消息发送的副作用字段（关系分数、记忆等）。

## 行为规范（端到端）

### 0) attempt 范围与前置步骤

- attempt 循环仅覆盖：LLM 调用、JSON 解析、L0/L1 校验裁剪、attempt 落库、重试等待与抢占检查。
- 不进入 attempt 循环的前置步骤（仅执行一次）：实例/联系人校验、关系查询、Prompt 与上下文构建、配置选择与参数组装。
- 目标：避免重复执行步骤 3-7 带来的额外延迟与副作用风险。

### 1) attempt 生命周期

1. 检查 turn 是否仍活跃（延迟抢占 guard）。
2. 调用 LLM（请求侧仍携带完整运行时 schema；运行时 gate 仅做 L0）。
3. 解析响应为 JSON dict：
   - 失败 → attempt 失败（进入重试）。
4. L0 校验：
   - 失败 → attempt 失败（进入重试）。
   - 通过 → 进入步骤 5。
5. L1 校验与裁剪：
   - `score` 不合法 → 移除 `score`（整项跳过）。
   - `memory_operations` 不合法 → 移除 `should_update_memory` 与 `memory_operations`（整项跳过）。
6. 落库 attempt 的 `ai_request_logs`（成功/失败均落库；成功时记录裁剪后有效响应；失败时记录失败原因、原始响应片段与请求载荷）。
7. 若 turn 已被抢占：
   - 立即停止，不发送消息，不执行 L1 副作用，不进入重试。
8. 消息发送：
   - `should_reply=true`：按 `outgoing_messages` 立即发送；按 `followup_messages` 延迟发送。
   - `should_reply=false`：不发送任何消息；但允许执行 L1 副作用（见下文）。
9. L1 副作用执行（关系/记忆等）：
   - 必须再次检查 turn 活跃性；被抢占则跳过。
   - `score` 存在且合法时才执行关系更新；不存在则跳过。
   - `should_update_memory=true` 且 `memory_operations` 合法时才执行记忆更新；否则跳过。
   - `should_reply=false` 路径下，副作用执行前必须在实际执行入口做 `is_active_turn` 检查（不可仅依赖发送链路检查）。
10. finalize buffer：由发送/终止路径统一推进到 `COMPLETE`。

### 2) 抢占（新消息优先）

- attempt 开始前、每次重试等待前、以及准备发送/执行副作用前均需执行 `is_active_turn` 检查。
- 抢占后行为：
  - 立即停止当前 attempt 的后续步骤；
  - 不再发起新 attempt（不重试）；
  - 不发送 `CHAT_INFO`；
  - buffer 终态由抢占链路走 `CANCELLED` 或由新窗口接管推进。

### 3) backoff 规则（已定）

- 使用固定间隔 backoff，不使用指数退避。
- 每次可重试失败后等待 `ai_llm_min_contract_retry_backoff_ms` 再进入下一次 attempt。
- 进入等待前与等待后都必须执行 `is_active_turn` 检查，若被抢占立即终止重试链路。

## L0 最小契约定义

### 实现约束

- L0 校验器必须是纯函数：输入为响应 payload 与 L0 规则定义，输出为校验结果与错误码；不得依赖 db/session。
- 现有同名校验函数需去歧义：
  - `app.services.llm.client.validate_ai_response`（含 db，上游链路检查）
  - `app.services.ai.utils.validator.validate_ai_response`（纯校验）
- 本方案要求为最小契约引入独立命名组件（例如 `l0_contract_validator`），禁止复用同名入口导致语义混淆。

### 必须字段

- `attack_detected: boolean`
- `should_block: boolean`
- `should_reply: boolean`

### 消息字段规则

- `outgoing_messages`：
  - 必须为 `string[]`（不接受单个 string 自动提升为数组）。
  - 元素必须为非空字符串（`len(strip()) > 0`）。
- `followup_messages`：
  - 同上。
- 当 `should_reply=true`：
  - `outgoing_messages` 与 `followup_messages` 至少有一个为非空数组；否则 L0 失败。
- 当 `should_reply=false`：
  - 允许两者缺失或为空数组；
  - 若存在且为合法数组，按“回复开关”语义不发送（见常量开关）。

### 常量开关：`should_reply=false` 且返回了合法消息数组

提供代码级常量开关以支持两种模式切换（不走 `system_config`）：

- 模式 B（默认）：不视为 L0 错误；忽略消息数组，不发送。
- 模式 A（严格）：视为 L0 错误；进入重试。

## L1 可选字段定义

### score（整项跳过）

- 校验失败条件（任一命中则移除整项 `score`）：
  - 非 object；
  - 维度集合不完整或存在多余维度；
  - 任一维度非整数；
  - 任一维度不在 `[minimum, maximum]`（取自 personality schema）。

### memory（整项跳过）

- `should_update_memory` 非 boolean、或 `memory_operations` 非法结构时，移除整项记忆字段，不执行记忆副作用。

## 数据落库与失败标记（最小闭环）

### 职责与单点落库

- attempt 日志的落库职责必须保持单点，避免重复写入与 `llm_request_id` 归属不清。
- 本方案要求：**由 `conversation_flow` 统一写入每个 attempt 的 `ai_request_logs`**。
- `llm_request_id` 绑定规则：
  - 仅“最终成功 attempt 的 `ai_request_logs.id`”绑定到 assistant outbound 消息（`message_history.llm_request_id`）。
  - 失败 attempt 的 `ai_request_logs.id` 不绑定任何消息，仅用于审计与诊断。

### ai_request_logs

- 每个 attempt 写入一条 `ai_request_logs`：
  - `status`：成功为 `SUCCESS`，失败为 `FAILED`（超时按错误类型映射）。
  - `response_time`：按 attempt 独立记录，不做跨 attempt 累计。
  - `request`：记录实际请求载荷（含 model/provider/streaming/overrides 等）。
  - `response`：记录裁剪后的可用响应；失败 attempt 记录解析失败信息、必要原始片段与诊断上下文。
  - `response.__min_contract`：写入最小契约诊断字段（attempt_index、attempt_total、failure_code、failure_detail、l0_ok、l1_score_kept、l1_memory_kept、preempted 等）。

### buffer 终态

- attempt 全部失败的静默失败路径：finalize 当前 LOCKED buffer 为 `COMPLETE`。
- 抢占路径：按抢占链路终止，不引入额外 finalize 行为。

## system_config 接线

必须新增并接线（缺失/类型不对按配置错误处理，不允许静默回退）：

- `ai_llm_min_contract_retry_enabled`（bool）
- `ai_llm_min_contract_retry_max_attempts`（int）
- `ai_llm_min_contract_retry_backoff_ms`（int）
- 取值约束：
  - `ai_llm_min_contract_retry_max_attempts >= 1`
  - `ai_llm_min_contract_retry_backoff_ms >= 0`
- 缺失/类型错误处理：fail-fast。
  - 读取配置时抛出配置错误并终止当前 turn。
  - 不允许使用默认值或隐式回退继续执行。
  - 错误必须写入可检索日志与 attempt 失败审计记录。

## 需改动的实现范围（代码级）

- `conversation_flow`：
  - 引入 attempt 循环、L0/L1 校验（手工裁剪）、重试与抢占 guard、静默失败终态推进、attempt 落库调用。
  - 调用 LLM 时不得依赖 `invoke_llm_with_validation` 的“整包 schema 校验”返回（该层会在校验失败时丢失关键审计字段）；改为在编排层统一解析与校验。
  - 新增失败 attempt 的显式落库调用点（不经过发送处理链路）。
- `llm_response_handler`：
  - 支持 `should_reply=false` 时仍可执行 L1 副作用（关系/记忆），但必须受 L1 校验与抢占 guard 约束。
  - 保持 followup 的独立发送语义（不将 followup 作为 outgoing 发送）。
  - 不得重复写入 `ai_request_logs`；仅接收“最终成功 attempt 的 `llm_request_id`”用于消息绑定与后续链路传递。
- 公共校验/归一化逻辑：
  - 合并重复的 `_normalize_memory_operations` 实现，避免 `conversation_flow` 与 `llm_response_handler` 双份维护。
- `transactions.save_ai_request_log`：允许记录最小契约诊断字段（写入 `response.__min_contract`）。
- `system_config`：读取并校验三项配置；确保调用链可追溯。

## 需同步更新的文档（实施阶段执行）

> 仅在代码落地并验证通过后同步更新 spec，保证 spec 与实现一致。

- `docs/spec/ai/llm-interaction.md`：将“整包 schema 闸门”调整为“L0 闸门 + L1 尽力处理”。
- `docs/spec/ai/conversation-flow.md`：更新全局失败边界与副作用执行规则（含抢占后不重试、静默失败终态）。
- `docs/spec/ai/relationship-system.md`：补充“score 校验失败整项跳过，不更新关系”。
- `docs/spec/ai/message-sending.md`：同步 `should_reply=false` 下副作用执行规则与首条发送门槛适用边界。

## 实施任务（实施阶段执行）

1. 新增 L0/L1 校验器与错误码约定（最小契约诊断字段）。
2. 在对话编排中加入 attempt 循环与抢占 guard（含 backoff）。
3. 统一 attempt 落库：由 `conversation_flow` 写 `ai_request_logs`；仅最终成功 attempt 的 `log_id` 绑定消息。
4. 新增失败 attempt 的落库调用点：覆盖 JSON 解析失败、L0 失败、传输失败/超时。
5. 调整响应处理：`should_reply=false` 时仍按 L1 规则执行副作用，并在副作用执行入口增加抢占 guard。
6. 落库字段：每个 attempt 写 `response.__min_contract`，确保失败 attempt 保留 `request_payload/raw_content/model/...` 等关键审计字段。
7. 合并重复的 `_normalize_memory_operations` 到单一实现。
8. 静默失败终态：finalize buffer 为 `COMPLETE` 并清理 pending。
9. 增加系统配置三项 key，并在 init SQL 与数据字典中同步（含取值范围校验）。
10. 增加测试：覆盖 L0 失败重试、抢占中断不重试、L1 跳过不阻断发送、followup-only 发送语义、should_reply=false 副作用执行、失败 attempt 落库与 attempt 独立 response_time 记录。

## 验收标准

- L1 字段（`score` 越界、`memory_operations` 非法）不会阻断消息发送；对应副作用被整项跳过且有可审计日志。
- L0 失败触发重试，且最多 `max_attempts` 次；重试期间发生抢占则停止且不再重试。
- attempt 全部失败时用户侧静默（无 `CHAT_INFO`），但：
  - buffer 被 finalize 为 `COMPLETE`；
  - `ai_request_logs` 存在完整 attempt 记录与 `__min_contract` 诊断字段；
  - 可明确检索到失败标记（status=FAILED）。
- `should_reply=true` 且仅 followup 非空：仅按 followup 延迟流程发送，不发送 outgoing。
- `should_reply=false`：不发送消息，但在未抢占情况下仍可执行合法 L1 副作用。
- `system_config` 三项 key 缺失/类型错误时，链路不会静默回退，错误可定位。
