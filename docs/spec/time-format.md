# 时间格式规范

本项目使用两种时间格式，根据字段类型和用途区分：

## 1. Schema 时间字段（ISO8601 字符串）

**适用场景**：Pydantic Schema 中的 `datetime` 类型字段

**格式**：ISO8601 字符串（FastAPI 自动序列化）

**示例字段**：
- `created_at` - 记录创建时间
- `updated_at` - 记录更新时间
- `expires_at` - 过期时间
- `confirmed_at` - 确认时间

**示例值**：
```json
{
  "created_at": "2026-02-14T12:52:07.995682+00:00",
  "updated_at": "2026-02-14T12:52:07+08:00"
}
```

**说明**：
- 符合 ISO8601 标准，可读性强
- **必须包含时区信息**（推荐统一使用 UTC：`Z` 或 `+00:00`）
- JavaScript 原生支持：`new Date("2026-02-14T12:52:07.995682+00:00")`

## 2. 业务时间戳字段（Unix 毫秒整数）

**适用场景**：消息系统、实时通信、客户端时间上送

**格式**：Unix 毫秒时间戳（整数）

**示例字段**：
- `sent_time_ms` - 消息发送时间（服务端认定）
- `client_sent_time_ms` - 客户端发送时间
- `server_time_ms` - 服务器当前时间
- `time_ms` - 事件时间
- `timestamp` - 协议时间戳

**示例值**：
```json
{
  "sent_time_ms": 1710001111333,
  "client_sent_time_ms": 1710001111222,
  "server_time_ms": 1710001112000
}
```

**说明**：
- 用于高精度时间排序和游标推进
- 字段名通常带 `_ms` 后缀表示毫秒精度
- 便于客户端直接进行数值比较和计算

## 命名约定

- **ISO8601 字段**：使用 `_at` 后缀（如 `created_at`）
- **毫秒时间戳字段**：优先使用 `*_time_ms`（如 `sent_time_ms`、`client_sent_time_ms`）、`time_ms` 或 `timestamp`
- **到期/截止时间字段**：允许使用 `*_expires_at_ms`（如 `lease_expires_at_ms`、`buffer_expires_at_ms`）
- **对外 API 命名约束**：禁止新增通用 `_at_ms` 字段命名（如 `sent_at_ms`）；内部事件结构字段名允许使用 `_at_ms`
