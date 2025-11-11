# AI 消息处理技术文档（MVP 版）

本技术文档明确 AI 消息缓冲聚合、可抢占处理、并发与幂等策略，以及与数据库字段的对应关系。作为实现基线，代码与 SQL 以本稿为准（获批后落地）。

## 目标

- 简洁：最少字段完成聚合与可抢占处理（KISS/YAGNI）。
- 可抢占：新消息到期后直接覆盖旧处理，不被旧请求阻塞。
- 幂等：结果落地前二次校验，旧请求结果丢弃。
- 易扩展：后续若需完整合并明细，可加关系表，无需改现有字段。

## 数据表与字段（ai_contexts 相关）

约束与索引建议

- 仅 user 消息使用状态：
  `CHECK ((role = 2 AND aggregate_state IS NOT NULL) OR (role <> 2 AND aggregate_state IS NULL))`
- 同会话唯一锁（限制活跃处理窗口）：
  `UNIQUE(user_qiao_id, character_qiao_id) WHERE role=2 AND aggregate_state=2`
- 到期扫描索引：
  `(user_qiao_id, character_qiao_id, buffer_expires_at_ms) WHERE role=2 AND aggregate_state=1`
- 计时状态字段：
  `micro_expires_at_ms`（微计时器）、`macro_expires_at_ms`（宏计时器）以及 `last_message_category`（上一条消息类别）
- 时间基准：聚合到期相关计算/比较统一使用数据库时钟
  `NOW()` → `(EXTRACT(EPOCH FROM NOW())*1000)::BIGINT`

实现要点（简述）

- 新消息到达：若存在“最近一条 role=user 且 state=OPEN”窗口，则仅更新 `content/last_msg_time_ms/last_msg_id_client/buffer_expires_at_ms`；否则新建一条 `OPEN` 窗口。
- 触发处理（到期）：在事务内先将该会话所有旧的 `OPEN/LOCKED` 标记为 `CANCELLED`，再将“最新且到期”的窗口置为 `LOCKED`，随后启动处理。
- 结果落地前校验：仅当该窗口仍为 `LOCKED` 时写入 ASSISTANT 并将其置为 `COMPLETE`；否则丢弃（被抢占的旧结果）。
- assistant 行不使用状态字段，避免无意义更新。

设计动机

- 以状态机+唯一锁实现“新消息可抢占旧处理”，无需进程内锁与复杂协调。

## 整体流程

1) 入站缓冲（add_message_to_buffer）

- 输入：用户消息（含 client 侧 `msg_id`、是否支持 typing、时间戳等）。
- 逻辑：
  - 查询“最近一条 user 且 state=OPEN”的窗口；存在则合并：
    - 仅更新：`content/last_msg_time_ms/last_msg_id_client/buffer_expires_at_ms`
  - 否则创建新窗口（state=OPEN，`first/last_msg_id_client` 同步设置，`buffer_expires_at_ms=now+wait`）。
- 等待时间：依据 supports_typing 与消息类型配置；建议在 SQL 中用 DB 时钟计算到期时间。

2) 到期扫描与锁定（scheduler tick）

- 周期性扫描：`role=user AND state=OPEN AND buffer_expires_at_ms <= now_ms_db`。
- 对每个会话：开启事务，执行“抢占式锁定”：
  - 先将该会话所有旧的 `OPEN/LOCKED` 行批量置 `CANCELLED`；
  - 再将“最新且到期”的窗口置 `LOCKED`；
  - 唯一部分索引保证同会话最多一个 `LOCKED`，并发下失败方重试。

3) 执行与落地（processor）

- 读取 `LOCKED` 窗口，构建上下文，发起 Doubao 流式请求（SSE）。
- 若新窗口抢占发生，立即中止流式读取（早停可减少后续输出 tokens 费用）。
- 结果落地前二次校验：若该窗口仍为 `LOCKED`，则：
  - 写入一条 `role=assistant` 的上下文行；
  - 将该 user 窗口置 `COMPLETE`。
- 若状态已变（CANCELLED/OPEN/不存在），丢弃结果（被抢占）。

4) 发送与失败重试

- 通过 LeanCloud 发送；失败写入 `message_delivery_failures`，按既有策略重试。

## Doubao 调用策略（与计费）

- 一律使用“流式输出” + 早停（SSE）：
  - 可以在“满足需求/被抢占”时立即停止，节省后续输出 tokens（输入 tokens 不变）。
  - 参考：`stream_options.include_usage` / `chunk_include_usage` 监控用量。
- 控制最大输出：配置 `max_tokens`（或深度思考模型的 `max_completion_tokens`）防止超预算。
- 上下文缓存：结合 Doubao Context/Responses Cache 降低输入 tokens 成本（后续迭代接入）。

## 并发与时钟

- 并发安全：依赖数据库事务 + 唯一部分索引；不需要进程内 per-conversation 锁。
- 时钟一致性：建议到期时间的写入与扫描均用 DB 时钟，避免多实例时间漂移。

## 错误与恢复

- 重启恢复：扫描 `role=user AND state=OPEN AND buffer_expires_at_ms <= now_ms_db` 即可恢复处理。
- 异常滞留：定期清理长时间 `LOCKED` 的窗口（超限置 `CANCELLED` 或回到 `OPEN`），避免卡死（可在后续迭代加入）。

## 可选扩展（非 MVP）

- 合并明细关系表：`ai_context_sources(context_id, msg_id_client, seq_no, created_at)`，当需要精确审计每条合并消息时引入。
- 处理轨迹审计：如需，可增加 `locked_at/canceled_at/canceled_by_context_id` 等审计列（当前不必需）。

## 落地步骤（获批后）

1) 更新初始化 SQL：删除旧列、添加新列与索引、CHECK 约束；
2) 代码改造：
   - buffer：改为首/末 ID + 计数；去掉 JSON 解析；
   - scheduler：实现抢占式锁定事务；
   - processor：二次校验 + 流式早停；
3) 管理后台：展示 `aggregate_state/first&last_msg_id/buffer_expires_at_ms`；
4) 迁移脚本（如已有数据）：从旧 `source_message_ids/context_metadata` 回填新列（可选）。
