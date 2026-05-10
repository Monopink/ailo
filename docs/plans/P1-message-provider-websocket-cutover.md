# 用户消息传输切换到自研 WebSocket（一次性实施）

## 背景与目标

- 外部约束：LeanCloud 公告停服日期为 `2027-01-12`。
- 现状约束：用户侧消息传输仍依赖 LeanCloud；小程序端存在连接恢复稳定性问题。
- 本次目标：用户侧消息传输统一使用自研 WebSocket 通道，业务处理链路继续使用现有后端消息域实现（入站校验、落库、outbox、离线补偿、ACK）。

## 已确认决策

1. 本次任务不做里程碑拆分，按一次性实施执行。
2. 切换策略为一次性切换，不保留双通道并行路径。
3. 小程序发送交互保持当前语义：允许用户发送操作，先写本地 `SENDING`，发送失败标记为 `FAILED`，不以“禁止发送”替代失败标记。
4. 连接参数采用现行值：客户端 `ping` 周期维持 25 秒级，服务端 Presence lease TTL 维持 90 秒。
5. 本次不新增“连接数硬拒绝闸门”；容量治理通过监控告警与放量控制执行。
6. 扩容阈值用于运维决策，不在本次实现中新增自动扩缩容流程。
7. 监控与告警纳入实施范围，统一落到现有 `alert_events` 告警体系。
8. 清理 LeanCloud 冗余代码与文档，最终状态不保留用户消息传输的 LeanCloud 路径。
9. 数据库策略采用方案 A：保留多 provider 通用表结构（不收紧为 WS-only 约束）；仅清理 LeanCloud 运行配置项与对应代码依赖。
10. 管理后台不保留消息服务状态卡片，统一通过监控告警观测运行态。

## 当前实现核对（与本次改造直接相关）

- 后端已提供 WebSocket 用户消息端点：`GET /ws/messages`。
- 小程序发送链路已具备本地消息状态管理（`SENDING/SENT/FAILED/RECEIVED`）与失败重试。
- 后端 provider 工厂默认发送路径仍绑定 LeanCloud 实现。
- 非时间线通知发送仍经 `get_default_provider()` 直连 provider，当前实现依赖 LeanCloud。

## 实施范围

### 后端

- 消息 provider 默认实现改为 WebSocket 用户通道。
- 改造通知发送路径，移除对 LeanCloud 直发依赖。
- 保持离线补偿与 ACK 接口语义不变（仅返回时间线消息）。
- 增加 WebSocket 运行态监控指标采集与阈值告警写入。
- 管理后台移除消息服务状态卡片与 LeanCloud/Webhook 管理入口。

### 数据库

- 保留 `message_history`、`message_endpoints`、`message_deliveries`、`message_dispatch_outbox`、`message_devices` 的多 provider 通用字段与约束定义。
- 删除 LeanCloud 运行配置项（`leancloud_im_server_url`、`leancloud_im_service_conversation_id`、`leancloud_im_webhook_token`）及其管理端依赖入口。
- 不新增“WS-only 约束收紧”迁移。

### 小程序

- 以 WebSocket 适配器替换 LeanCloud 适配器作为唯一消息传输实现。
- 移除小程序侧对 `im_conv_id`、LeanCloud bootstrap、LeanCloud SDK 连接参数的运行时依赖。
- 保持发送失败标记、重试、离线补偿、ACK 行为语义不变。

### 文档

- 更新 `docs/spec/message/*`、`docs/api/*`、`frontend/mp-weixin/AGENTS.md` 中用户消息传输现态描述。
- 删除（按仓库规则迁移到 `deleted/`）与用户消息传输路径相关的 LeanCloud 专用文档与实现文件。

## 实施任务

### 1. 后端传输层收敛

- 在 `MessageProvider` 体系中落地 WebSocket 默认发送实现。
- 调整 `providers/factory.py` 与 `outbound/sender.py`，确保用户消息发送不再依赖 LeanCloud provider。
- 保留 endpoint 按 provider 分发能力，保证 `message_endpoints` 与 `message_deliveries` 语义一致。

### 2. 通知发送链路改造

- 将 `send_notification` 从“默认 provider 直发”改为“按活跃 endpoint 分发”的后端统一路径。
- 失败写入 `notification_push_history` 失败状态，成功写入发送结果。
- 通知不并入离线时间线接口返回范围。

### 3. 小程序消息适配器替换

- 新增 WebSocket adapter，实现 `auth/ping/send_message/typing/event/error` 协议。
- 重构 `adapter-types.ts` 与 `message/service.ts` 的 LeanCloud 专属字段与参数结构。
- 清理 `conversation-store` 中 LeanCloud 会话配置依赖，保留消息域所需最小状态。

### 4. 稳定性与监控告警

- 增加并接入以下监控指标（告警事件写入 `alert_events`）：
  - 活跃 WebSocket endpoint 数
  - `message_dispatch_outbox` 积压量（pending/processing）
  - WebSocket 发送失败计数（含 `ws_send_queue_full`、`WS_SEND_FAILED`）
  - 消息发送 ACK 延迟分位值（P95）
- 固定告警阈值：
  - 活跃 WebSocket endpoint 数：`1200`
  - `message_dispatch_outbox` 积压量（pending + processing）：`400`
  - WebSocket 发送失败计数（5 分钟窗口，`ws_send_queue_full + WS_SEND_FAILED`）：`20`
  - ACK 延迟 P95（10 分钟采样窗口）：`15000ms`
- 告警事件类型：
  - `MESSAGE_WS_ACTIVE_ENDPOINT_THRESHOLD_EXCEEDED`
  - `MESSAGE_WS_OUTBOX_BACKLOG_THRESHOLD_EXCEEDED`
  - `MESSAGE_WS_SEND_FAILURE_THRESHOLD_EXCEEDED`
  - `MESSAGE_WS_ACK_P95_THRESHOLD_EXCEEDED`

### 5. LeanCloud 代码与文档清理

- 清理用户消息路径下 LeanCloud API、service、adapter、配置项、文档引用。
- 按仓库规则处理文件移除：文件移动到 `deleted/`，不直接删除。
- 清理后保证仓库内用户消息主链路不存在 LeanCloud 运行依赖。

### 6. 数据库配置项清理

- 编写 Alembic 迁移移除 LeanCloud 运行配置项，并同步更新 `backend/database/bootstrap/base.sql`。
- 清理管理端系统配置接口中对应配置项的读写与展示入口。
- 保持消息核心表结构不变。

## 验收标准

1. 小程序端发送/接收/输入态在 WebSocket 通道可用，发送失败表现为 `FAILED` 状态且支持重试。
2. 用户消息传输链路不调用 LeanCloud SDK/REST/Webhook。
3. 离线补偿与 ACK 接口行为保持既有契约。
4. 监控指标可观测，阈值触发时可在 `alert_events` 查询到对应告警事件。
5. 用户消息传输相关文档与代码现态一致，不存在 LeanCloud 运行路径描述。
6. 数据库中不存在 LeanCloud 消息运行配置项；消息核心表结构保持多 provider 通用定义。

## 实施结果

- 当前状态：已完成（更新日期：`2026-05-10`）。
- 已完成：
  - `docs/spec/message/*` 与 `docs/api/*` 的消息传输现态改为 WebSocket-only，并移除 LeanCloud 专用文档入口。
  - 管理后台仪表盘与系统设置页移除消息状态卡片及 LeanCloud/Webhook 管理区。
  - 后端消息分发默认 provider 切换为 WebSocket，通知发送链路改为 WS 事件下发。
  - LeanCloud API/provider/schema 运行时代码按规则迁移到 `deleted/`，并清理主链路引用。
  - `backend/database/bootstrap/*` 已移除 LeanCloud 运行配置项种子数据。
  - Alembic 迁移 `backend/alembic/versions/20260510_01_remove_leancloud_message_runtime_configs.py` 已落地，清理 `system_configs` 中 `leancloud_im_server_url`、`leancloud_im_service_conversation_id`、`leancloud_im_webhook_token`。
  - 小程序消息适配器切换为 WebSocket 实现，移除 `/lc-im/bootstrap` 与 LeanCloud SDK 运行时依赖。
  - 小程序 TypeScript 校验通过（`npm run type-check`）。
  - WebSocket 阈值告警 worker 已接入应用生命周期，阈值事件已落地到 `alert_events`。
  - `2026-05-09` 验证记录（容器环境）：
    - 触发命令：`docker exec backend python -c "import asyncio; from app.core.config import get_settings; from app.utils.snowflake import init_snowflake; from app.services.message.monitoring import alerting as m; s=get_settings(); init_snowflake(s.SNOWFLAKE_DATACENTER_ID, s.SNOWFLAKE_MACHINE_ID); m._ACTIVE_ENDPOINT_THRESHOLD=0; m._OUTBOX_BACKLOG_THRESHOLD=0; m._SEND_FAILURE_THRESHOLD=0; m._ACK_P95_THRESHOLD_MS=0; asyncio.run(m._run_once())"`
    - ACK P95 触发命令：`docker exec backend python -c "import asyncio; from app.core.config import get_settings; from app.utils.snowflake import init_snowflake; from app.services.message.monitoring import alerting as m; s=get_settings(); init_snowflake(s.SNOWFLAKE_DATACENTER_ID, s.SNOWFLAKE_MACHINE_ID); m._ack_p95_latency_ms = lambda db, *, now: asyncio.sleep(0, result=20001.0); m._ACTIVE_ENDPOINT_THRESHOLD=999999999; m._OUTBOX_BACKLOG_THRESHOLD=999999999; m._SEND_FAILURE_THRESHOLD=999999999; m._ACK_P95_THRESHOLD_MS=15000; asyncio.run(m._run_once())"`
    - 查询命令：`docker exec postgres psql -U ailo_user -d ailo -c "select event_type, domain, severity_level, details->>'metric_name' as metric_name, details->>'metric_value' as metric_value, created_at from alert_events where event_type like 'MESSAGE_WS_%' order by created_at desc limit 10;"`
    - 查询结果包含：
      - `MESSAGE_WS_ACTIVE_ENDPOINT_THRESHOLD_EXCEEDED`
      - `MESSAGE_WS_OUTBOX_BACKLOG_THRESHOLD_EXCEEDED`
      - `MESSAGE_WS_SEND_FAILURE_THRESHOLD_EXCEEDED`
      - `MESSAGE_WS_ACK_P95_THRESHOLD_EXCEEDED`
