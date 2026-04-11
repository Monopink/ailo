# Message Buffer：Wake 动态审计 + Typing 时序修正 + Wake 串行叠加（旧版体感）

## 目标

- 修复“小程序端 typing 展示时序反直觉（清空输入后才出现对方 typing）”问题，使 typing 事件按对端 `sent_time` 作为权威时序处理。
- 将 Wake 与 buffer 计时从“门控 max”调整为“串行叠加”等待语义（对齐旧版体感）。
- 保留 Wake 动态调整机制（`wake_time_adjustment`），并**新增数据库审计**记录每次 wake 动态计算结果，便于排障与验收。
- 增强后端可观测性：关键路径输出足够的结构化 INFO 日志以还原每次计时与 wake 计算。

## 现状

- 后端 buffer 调度以 `buffer_expires_at_ms` 为唯一截止时间，旧实现将 wake 作为绝对门控参与计算（`max(wake_expires_at_ms, timer_due_ms)`）。
- `ai_message_buffer` 仅保存 wake 的“当前值”（旧字段 `wake_expires_at_ms`，新语义为 `wake_delay_ms`）与计数（`wake_adjustment_count`），且在进入 `LOCKED` 时会清空 timer/wake 字段，无法事后追溯 wake 计算过程。
- 小程序端 typing presence 使用 `received_time = Date.now()` 作为去重/丢弃基准，导致 typing 事件在链路延迟下出现“晚显示/反直觉显示”的稳定问题。

## 问题点

- Wake 动态计算缺乏持久化审计：无法回答“本轮 wake 为什么变长/变短、随机因子是多少、调整前后数值是什么”。
- 小程序 typing 时序基准不稳定：使用 `received_time` 会把链路延迟直接放大为 UI 时序错觉。
- Wake 与 buffer 等待语义与旧版体感不一致：旧版表现更接近“先等 buffer/timer，再等 wakeup”，而现版为“取更晚者”。

## 需求点（已确认）

1. Wake 与 buffer 等待采用旧版体感：**串行叠加，不并行**。
2. typing 消息暂不用于撤销本轮 lock（不引入“reopen window/撤销 lock”逻辑）。
3. 小程序 typing 事件以 `sent_time` 作为权威时序。
4. 新增 wake 动态计算结果的数据库审计表，表名：`ai_buffer_wake_events`。

## 方案概述

### A) 数据库：新增 Wake 审计表（append-only）

新增表：`ai_buffer_wake_events`

- 一次 wake “创建/调整”对应一条事件记录。
- 记录当次使用的关系参数快照、调整模式、随机数、调整前后 remaining 与 expires 等关键字段。
- 不影响现有 `ai_message_buffer` 状态机职责（仍为“当前窗口状态快照”）。

建议字段（最小可用集，后续可裁剪/补充）：

- `id`（BIGINT，snowflake）
- `buffer_id`（BIGINT，索引）
- `user_qiao_id`（VARCHAR(32)）
- `instance_qiao_id`（VARCHAR(32)）
- `event_time_ms`（BIGINT，DB now ms）
- `reason`（VARCHAR(32)：`created` / `adjusted`）
- `trigger_message_type`（SMALLINT：TEXT/TYPING_START/TYPING_END）
- `prev_wake_delay_ms`（INTEGER，nullable）
- `new_wake_delay_ms`（INTEGER，nullable）
- `micro_expires_at_ms`（BIGINT，nullable）
- `macro_expires_at_ms`（BIGINT，nullable）
- `buffer_expires_at_ms`（BIGINT，nullable）
- `adjustment_mode`（VARCHAR(32)）
- `wake_time_min_ms`（INTEGER）
- `wake_time_max_ms`（INTEGER）
- `wake_time_bias`（VARCHAR(32)）
- `random_number`（INTEGER，nullable，仅 random_half）
- `wake_adjustment_count_after`（SMALLINT）
- `created_at`（TIMESTAMPTZ, default now）

索引建议：

- `idx_ai_buffer_wake_events_buffer_time`：`(buffer_id, created_at)`
- 可选：`(user_qiao_id, instance_qiao_id, created_at)`

### B) 后端：Wake 串行叠加语义

- 更新 `docs/spec/message/buffer.md`：将 Wake 与 timer 的组合语义调整为“串行叠加”（旧版体感），并明确保留 wake 动态调整的作用点与边界。
- 更新实现：调整 `buffer_expires_at_ms` 的计算与状态机字段写入，使其表达“timer_due + wake_delay”的语义（细节以实现阶段最终定稿为准）。

约束：

- 不引入 typing 撤销 lock / reopen window。

### C) 前端（小程序）：Typing 时序修正

- Typing presence 去重/丢弃基准改用对端 `sent_time` 作为权威时序；必要时用 `received_time` 做异常保护。
- 目标：避免“typing 迟到导致晚显示/被丢弃”，并使 UI 表现符合用户直觉。

### D) 可观测性增强（后端）

在 buffer 关键路径增加结构化 INFO 日志（不依赖 DEBUG）：

- 窗口创建/更新：输出 `now_ms/micro/macro/wake/buffer_expires_at_ms/last_category/message_type/msg_id_client`。
- wake 调整：输出 `prev_wake_delay_ms/new_wake_delay_ms/adjustment_mode/random_number/buffer_expires_at_ms`。
- wake 调整：输出 `prev_wake_delay_ms/new_wake_delay_ms/adjustment_mode/random_number/buffer_expires_at_ms`。
- lock：输出 `locked_buffer_id/lock_now_ms/(lock 时的) last_category/turn_version` 等。

## 实施步骤（执行前提：用户明确批准开始动手）

1. 文档对齐
- 更新 `docs/spec/message/buffer.md`（wake 串行叠加语义）。
- 如需补充 typing 时序规则，更新 `docs/spec/message/typing.md`（仅写客户端可依赖行为）。

2. 数据库变更
- 增加 SQLAlchemy model（`backend/app/models/ai/*` 适配现有结构）。
- 新增 Alembic migration 创建 `ai_buffer_wake_events` 表与索引。
- 使用生成流程同步 `docs/data-dict/*`（禁止手工双写）。

3. 后端实现
- 在 wake 创建与 wake 调整路径写入 `ai_buffer_wake_events`。
- 调整 wake+timer 组合语义实现（对齐文档）。
- 增强 INFO 日志（仅增加必要字段，不输出敏感信息）。

4. 小程序实现
- 调整 typing presence 的去重/丢弃规则，使用 `sent_time` 作为权威时序。

5. 验证
- 复现脚本：发送 TEXT 后立即输入（触发 typing_start），观察处理是否延后；清空输入时不应出现“清空后才突然显示对方 typing”的反直觉现象。
- 数据核验：`ai_buffer_wake_events` 中每次 created/adjusted 均有记录，字段可解释且与 buffer 行为一致。
- 日志核验：可从 INFO 日志还原当次计时器/wake 的计算链路。

## 验收标准

- 小程序 typing 展示按 `sent_time` 时序稳定工作，不出现“清空后才出现对方 typing”的反直觉表现。
- Wake 计算过程可追溯：每次 wake 创建/调整在 `ai_buffer_wake_events` 中有可解释记录。
- Wake 与 timer 的组合语义与旧版体感一致（串行叠加），并在 `docs/spec/message/buffer.md` 中有明确、无歧义描述。
- 后端 INFO 日志足以定位“是否在 lock 前生效、是否发生调整、调整原因是什么”等关键问题。

## 相关文件

- Spec：`docs/spec/message/buffer.md`、`docs/spec/message/typing.md`
- 后端：`backend/app/services/message/processing/buffer.py`、`backend/app/services/message/processing/scanner.py`
- 小程序：`frontend/mp-weixin/utils/message/conversation-presence-store.ts`、`frontend/mp-weixin/utils/message/service.ts`
- 数据：`backend/app/models/ai/instance.py`（buffer model 所在）、Alembic migrations、`docs/data-dict/*`
