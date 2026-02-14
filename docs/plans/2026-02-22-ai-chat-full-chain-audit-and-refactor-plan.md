# Task: AI 对话完整链路审查与重构方案（原始体验对齐，2026-02-22）

## 1. 任务目标

将当前 AI 聊天链路重构为“原始体验对齐 + 数据库一致性语义”版本，覆盖从入站到发送落库的完整闭环。

实施范围：

1. 入站事件分类与缓冲
2. buffer 锁定与抢占
3. LLM 请求中止与结果丢弃
4. 发送中断与 pending 语义
5. 副作用执行顺序与门槛
6. 文档与数据字典同步

## 2. 体验与并发基线（强约束）

1. `typing_start/typing_end` 只影响计时，不触发中断。
2. `CONTENT_INPUT` 到达时立即入缓冲并记录新入站代次，但不立即停止旧发送。
3. 新窗口到期并锁定后，才切换活跃代次并抢占旧请求/旧发送。
4. 抢占后旧代次不得产生外显 assistant 回复。
5. `pending_messages` 仅保留未发送 `outgoing`，不保留 `followup`。
6. Wake 仅影响“何时开始处理”，但 typing 事件在 wake 等待期仍必须重置计时。

## 3. 已确认偏差

### A（P0）typing 错误触发发送中断

证据：`backend/app/services/message/processing/buffer.py:101`

### B（P0）抢占闭环不完整（含非流式）

1. 抢占检查仅在流式启用时接入
   证据：`backend/app/services/ai/orchestrators/conversation_flow.py:465`
2. finalize 失败后仍可能进入发送路径
   证据：`backend/app/services/ai/orchestrators/llm_response_handler.py:100`、`backend/app/services/ai/orchestrators/llm_response_handler.py:142`

### C（P0）锁定逻辑会批量取消 OPEN

证据：`backend/app/services/message/processing/buffer.py:201`

### D（P1）typing_start 缺少 short + total 双计时语义

证据：`deleted/backend/app/services/ai-chat/models/model_ailo.py:729`、`backend/app/services/message/processing/buffer.py:973`

### E（P1）发送中断边界与原始体验不一致

当前实现为内容入站即中断发送；目标体验为“内容入站后等待新窗口到期再切换代次抢占”。

### F（P1）副作用顺序与门槛偏差

当前会话副作用在发送前执行，不满足“首条发送门槛后执行”约束。

### G（P2）发送中断依赖进程内状态

证据：`backend/app/services/message/processing/sender.py:24`

## 4. 最终方案

### 4.1 事件语义分层

内部事件意图：

1. `CONTENT_INPUT`：文本、图片、音频等内容型输入
2. `INPUT_HINT`：`typing_start`、`typing_end`
3. `CONTROL`：系统控制事件

执行规则：

1. 仅 `CONTENT_INPUT` 推进入站代次。
2. `INPUT_HINT` 仅更新 buffer 计时器。

### 4.2 代次真相源：双代次模型

表：`ai_conversation_runtime`

字段：

1. `ingress_version`：内容入站代次（`CONTENT_INPUT` 到达即原子自增）
2. `active_turn_version`：活跃处理代次（仅在窗口锁定开始处理时推进）

执行规则：

1. 入站阶段：`CONTENT_INPUT` 原子自增 `ingress_version`。
2. 锁定阶段：最新到期窗口（`WAITING_WAKEUP` 或 `OPEN`）成功进入 `LOCKED` 后，原子将 `active_turn_version` 推进到当前 `ingress_version`。
3. 请求任务、发送任务绑定 `task_turn_version=active_turn_version`。
4. 请求与发送关键节点检查 `current_active_turn_version == task_turn_version`；不一致立即终止旧路径。

### 4.3 延迟生效抢占

1. 内容入站不会立即停止旧发送。
2. 新窗口到期并锁定后才生效抢占。
3. 该机制将用户体感切换延迟锚定在 buffer 等待时长（默认由 `message_buffer_normal_wait_ms` 控制）。

### 4.4 副作用分层与门槛

1. 安全副作用：`attack_detected`、`should_block`，始终执行。
2. 会话副作用：`memory_operations`、`score`，仅在“首条 assistant 消息发送成功且会话项落库成功”后执行。

### 4.5 pending_messages 边界

1. 仅记录“被抢占导致未发送”的业务事实。
2. 仅持久化未发送 `outgoing`。
3. `followup` 不写入 `pending_messages`。
4. Provider 投递失败走 outbox 重试链路，不写 `pending_messages`。
5. `should_reply=false` 清空 `pending_messages`。

### 4.6 Buffer 锁定规则

1. 锁定候选来自已到期窗口（`WAITING_WAKEUP` 或 `OPEN`）。
2. 仅允许最新到期窗口进入 `LOCKED`。
3. 旧 `LOCKED` 仅在新代次锁定成功后按抢占语义取消。
4. `WAITING_WAKEUP` 与 `OPEN` 使用同一截止时间语义，已到期即可参与锁竞争。
5. lock/finalize/cancel 均使用 CAS 条件更新。

## 5. 实施拆解

### 阶段 1：模型与事务接口

1. 新增/更新 `ai_conversation_runtime` 模型、初始化 SQL、数据字典（不新增迁移脚本）。
2. 落地 `ingress_version`、`active_turn_version` 原子操作接口。
3. 提供统一代次校验接口。

### 阶段 2：入站与 buffer

1. 入站事件分类接入 `CONTENT_INPUT/INPUT_HINT/CONTROL`。
2. 删除“入站即中断发送”路径。
3. 补齐 `typing_start` short + total 双计时语义（含配置键、初始化 SQL、数据字典同步）。
4. 重写 `lock_conversation_preemptively` 为 CAS 锁定流程。
5. 在锁定成功时推进 `active_turn_version` 并触发抢占生效。
6. 统一截止时间为 `buffer_expires_at_ms`，去除 `WAITING_WAKEUP -> OPEN` 的独立晋升分支。

### 阶段 3：conversation_flow 与 response_handler

1. 流式/非流式统一执行代次抢占校验。
2. LLM 返回后、副作用前执行强校验。
3. finalize 失败立即终止，不进入发送。
4. 调整顺序为“安全副作用 -> 发送 -> 门槛检查 -> 会话副作用”。

### 阶段 4：sender

1. 中断机制从进程内 event 迁移到 `active_turn_version` 校验。
2. `typing` 事件不触发中断。
3. 抢占中断时仅写未发送 `outgoing` 到 `pending_messages`。
4. Provider 投递失败不写 `pending_messages`。

### 阶段 5：文档与测试

1. 同步更新 `docs/spec/ai/message-sending.md`、`docs/spec/message/buffer.md`、`docs/data-dict/ai-conversation.md`。
2. 文档移除 `sending_task_id` 语义残留。
3. 增加链路级自动化测试矩阵。

## 6. 验收标准

1. DELIVERING 中收到 `typing_start/typing_end`，发送不中断。
2. DELIVERING 中收到 `CONTENT_INPUT`，旧代次不立即中断；新窗口到期并锁定后旧代次中断。
3. 非流式请求处理中收到新内容并完成新代次锁定，旧代次结果不得发送。
4. 并发压测下，不出现未到期 `OPEN` 被批量取消。
5. 抢占中断后，未发送 `outgoing` 进入 `pending_messages` 并可在下一轮注入。
6. `followup` 不进入 `pending_messages`。
7. Provider 投递失败不写 `pending_messages`，走 outbox 重试。
8. 首条发送前被抢占，仅安全副作用生效。
9. 首条发送后被抢占，已达门槛的会话副作用可保持已提交状态。
10. 文档不再包含 `sending_task_id` 语义。
11. `WAITING_WAKEUP` 期间收到 `typing_end` 时，LLM 最早触发时间应相对该 `typing_end` 至少延后 `message_buffer_typing_end_wait_ms`。

## 7. 产出清单

1. 重构代码：`buffer/scanner/conversation_flow/llm_response_handler/sender`
2. 数据模型与初始化 SQL：`ai_conversation_runtime`（双代次字段）
3. 文档同步：`spec/data-dict/api`
4. 自动化测试与验证报告
