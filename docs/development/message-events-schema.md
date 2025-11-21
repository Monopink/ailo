## Message Events Schema

本文件定义消息系统在“Webhook → 管线 → 缓冲/AI → 发送”各阶段共享的事件结构。本 schema 兼容
[docs/prototype/message-flow.md](../prototype/message-flow.md) 中的 LeanCloud 消息格式以及
[docs/prototype/api_design.md](../prototype/api_design.md) 的命名规范，作为所有模块（前端、Webhook
parser、缓冲、AI、发送器、日志）的唯一数据契约。

> **适用范围**
>
> - Webhook 接收的入站消息（InboundMessageEvent）
> - 系统／AI 发出的出站消息（OutboundMessageEvent）
> - 未来的 Typing/通知/系统提示事件，可在本 schema 基础上扩展

### 1. 版本与命名

- `schema_version`：当前文档版本，初始为 `1.0.0`，语义化版本号；字段必填。
- `event_type`：小写蛇形命名，用于区分 `inbound_message`、`outbound_message` 等。
- 所有时间均为 Unix 毫秒时间戳（参考 api_design.md）。
- 所有身份字段使用 `qiao_id`（对外 ID），数据库内部依旧存 Snowflake ID。

### 2. 公共字段

| 字段名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `schema_version` | string | ✅ | 文档版本，初始 `1.0.0` |
| `event_type` | string | ✅ | 事件类型，现支持 `inbound_message` / `outbound_message` |
| `message_type` | int | ✅ | 消息类别：`1=TEXT`, `2=TYPING_START`, `3=TYPING_END`, `4=CHAT_INFO`, `9=NOTIFICATION`（与 message-flow.md 保持一致） |
| `conversation_id` | string | ✅ | 系统内部 conv_id |
| `from_qiao_id` | string | ✅ | 发送方 qiao_id |
| `to_qiao_id` | string | ✅ | 接收方 qiao_id |
| `content` | string | ✅（部分类型可为空） | 文本内容；typing 类事件可为空字符串 |
| `sent_at_ms` | int | ✅ | 发送时间（毫秒），LeanCloud `createdAt` 或系统生成 |
| `msg_id_server` | string | ✅ | 服务端 Snowflake ID，入站由 pipeline 生成，出站在发送前生成 |
| `msg_id_client` | string/null | 条件 | 客户端生成的 ID，仅用户→系统消息必填 |
| `msg_id_provider_inbound` | string/null | 条件 | 第三方入站 ID（LeanCloud `msgId`） |
| `msg_id_provider_outbound` | string/null | 条件 | 第三方出站 ID（发送成功后回填） |
| `supports_typing` | bool | ✅ | 客户端是否支持 typing（见 message-flow.md） |
| `client_sent_time` | int/null | 条件 | 客户端发送时间；无则置 null |
| `metadata` | object | ✅ | 业务扩展字段（白名单见下） |
| `provider_metadata` | object | ✅ | 第三方原始字段，便于审计与追溯 |
| `metadata.encryption` | string/null | 条件 | 传输加密算法（如 `base64`），为空表示纯文本 |
| `metadata.encryption_version` | string/null | 条件 | 加密协议版本（当前为明文，App 阶段再启用） |

**metadata 白名单（可按需扩展）：**

- `action`：系统消息附带的 action 描述
- `notification_type`：通知类型枚举（与 enums.NotificationType 保持一致）
- `rate_limit_bucket`：速率限制统计窗口（例如 `"10s"` / `"60s"`）
- `encryption` / `encryption_version`：传输加密算法与版本，目前默认 `base64` 作为占位编码

非白名单字段需在实施前追加到文档，避免 metadata 再次退化为“任意 dict”。

### 3. InboundMessageEvent

LeanCloud Webhook 解析后的标准结构，进入统一管线。

```jsonc
{
  "schema_version": "1.0.0",
  "event_type": "inbound_message",
  "message_type": 1,
  "conversation_id": "conv_xyz789",
  "from_qiao_id": "qiao_user001",
  "to_qiao_id": "qiao_xm001",
  "content": "你好",
  "sent_at_ms": 1710001111222,
  "msg_id_server": "msg_223788765171154945",
  "msg_id_client": "client_1710001111222_abc123",
  "msg_id_provider_inbound": "nYH9iBSBS_uogCEgvZwE7Q",
  "msg_id_provider_outbound": null,
  "supports_typing": true,
  "client_sent_time": 1710001111222,
  "metadata": {
    "action": null,
    "notification_type": null,
    "rate_limit_bucket": "10s",
    "encryption": "base64",
    "encryption_version": "v1"
  },
  "provider_metadata": {
    "lc_from": "qiao_user001",
    "lc_conv_id": "68edda0a554ecc6e8843b246",
    "raw_webhook": "{...LeanCloud 原始 payload...}"
  }
}
```

**字段要求**

- `msg_id_client`：必填，来自 LeanCloud `data.msg_id`。若缺失需返回 400 以便客户端补发。
- `provider_metadata.raw_webhook`：建议保存原始 JSON 字符串，便于审计。
- Pipeline Deduplication：使用 `(conversation_id, msg_id_client)` 作为幂等键（参见 message-architecture-refactor.md）。

### 4. OutboundMessageEvent

AI/系统经 sender 发送前的结构，确保与 Inbound 一致，便于审计与重放。

```jsonc
{
  "schema_version": "1.0.0",
  "event_type": "outbound_message",
  "message_type": 4,
  "conversation_id": "conv_xyz789",
  "from_qiao_id": "qiao_xm001",
  "to_qiao_id": "qiao_user001",
  "content": "我在呢，刚才看到你发的消息啦～",
  "sent_at_ms": 1710002222333,
  "msg_id_server": "msg_223788765171155999",
  "msg_id_client": null,
  "msg_id_provider_inbound": null,
  "msg_id_provider_outbound": null,
  "supports_typing": true,
  "client_sent_time": null,
  "metadata": {
    "action": {
      "type": "navigate",
      "target": "contact_requests"
    },
    "notification_type": 2001,
    "rate_limit_bucket": "60s",
    "encryption": "base64",
    "encryption_version": "v1"
  },
  "provider_metadata": {
    "lc_conv_id": "68edda0a554ecc6e8843b246"
  }
}
```

**字段要求**

- `msg_id_server`：在调用 provider 前生成 Snowflake ID，用于 message_history 主键与 delivery_attempts 关联。
- `msg_id_provider_outbound`：发送成功后由 provider 回填（LeanCloud 返回的 `msgId`）。
- `metadata.action`、`metadata.notification_type`：只对 message_type=4/9 有意义；TEXT 消息可省略或置 null。
- Sender 必须在写入 message_history 时序列化整个事件，保证 future replay。

### 5. Typing / 控制事件

Typing Start/End 属于 `message_type=2/3` 的普通消息，遵循同一 schema，但 `content` 允许为空字符串。  
`metadata` 中可添加：

- `typing_state`: `"start"` / `"end"`
- `typing_sequence`: 客户端自增序号，方便前端对齐

### 6. Schema 与数据库映射

| Schema 字段 | message_history 列 | 说明 |
| --- | --- | --- |
| `msg_id_server` | `msg_id_server` | 唯一索引 |
| `msg_id_client` | `msg_id_client` | `(conversation_id, msg_id_client)` 唯一约束 |
| `msg_id_provider_inbound` | `msg_id_provider_inbound` | direction=INBOUND 时写入 |
| `msg_id_provider_outbound` | `msg_id_provider_outbound` | direction=OUTBOUND 时写入 |
| `metadata` | `message_metadata` | JSONB，入库前需校验白名单 |
| `provider_metadata` | `message_metadata.provider` 或另建审计表 | 建议存入 `message_metadata.provider` 子字段 |

### 7. 校验与演进

- Pydantic Model：在 `services/message/events.py`（待新增）实现 `BaseEvent`, `InboundMessageEvent`, `OutboundMessageEvent`，强制字段校验。
- JSON Schema：若前端/第三方需要对接，可基于上述模型导出 JSON Schema 文件。
- 版本演进：新增字段时提高 `schema_version` 次版本，并在本文档描述兼容策略；破坏性变更需提升主版本。

---

> **实现清单**（下一步工作）
>
> 1. 创建 `services/message/events.py`，实现与本 schema 一致的 Pydantic dataclass。
> 2. Webhook parser、sender、buffer、AI pipeline 统一接收/返回事件对象。
> 3. `provider_metadata.raw_webhook` 由 Webhook 模块负责存储，落库时只保留必要字段，完整原文写入审计表或对象存储（依据存储策略）。
> 4. `metadata.rate_limit_bucket` 由速率限制模块写入，便于日志/监控区分 10s 与 60s 限制。
- 传输加密：当前默认使用 Base64 作为占位编码，相关字段 `metadata.encryption/encryption_version` 表示算法与协议版本。未来切换到 AES-256-GCM 时，服务端会在 `metadata` 中附带 IV、key id 等信息，并在 `message_history.message_metadata` 持久化。

---
