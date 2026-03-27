# 业务告警事件

定义通用业务告警事件的落库结构。该模块用于记录“需要闭环处理/需要跨天追踪/需要运营检索”的业务告警事件，不用于存储所有异常与错误日志。

枚举字段定义规则见 [README.md](README.md)：取值集合以 `backend/app/enums/system.py` 为准。

## alert_events

通用业务告警事件表（审计型、追加写）。

```txt
id -- Snowflake ID
event_type -- 事件类型（enum: AlertEventType）
domain -- 业务域（enum: AlertDomain）
severity_level -- 严重程度（enum: AlertSeverityLevel；与 Python logging level 对齐，允许：10/20/30/40/50）
dedupe_key -- 去重键（可为空；非空时参与 (event_type, dedupe_key) 去重）
details -- JSONB 详情（必须包含 schema_version；大小限制 16KB；禁止写入用户原文消息）
created_at
```

索引与约束（口径）：

- `(event_type, created_at DESC)`
- `(domain, created_at DESC)`
- `(created_at)`
- 部分唯一：`(event_type, dedupe_key)` 且 `dedupe_key IS NOT NULL`

## alert_event_entities

业务告警事件关联实体表，用于将事件关联到任意业务实体，便于检索与聚合。

```txt
id -- Snowflake ID
event_id -- 关联 alert_events.id
entity_type -- 实体类型（enum: AlertEntityType）
entity_id -- 实体 ID（string；统一承载 bigint/uuid/qiao_id）
created_at
```

索引（口径）：

- `(event_id)`
- `(entity_type, entity_id, created_at DESC)`
