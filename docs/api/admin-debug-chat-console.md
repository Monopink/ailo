# 管理端 Debug API（Chat Console）

本文档描述 Chat Console 使用的管理端调试接口。

> 约束：所有接口都要求 **Starlette-Admin 会话已登录**
>
> 精度约束：`llm_request_id` 对应 Snowflake BigInt。为避免前端 JS Number 精度丢失，API 统一使用 **字符串** 传输该字段。

---

## 1) 批量查询 LLM 映射关系

- **Method / Path**: `POST /admin-api/debug/messages/llm-links`
- **用途**: 按 `msg_id_server` 批量查询 `llm_request_id`

### Request

```json
{
  "msg_id_servers": [
    "msg_273338979288485888",
    "msg_273338979288485889"
  ]
}
```

### Response

```json
{
  "links": [
    {
      "msg_id_server": "msg_273338979288485888",
      "llm_request_id": "273338979288485888"
    },
    {
      "msg_id_server": "msg_273338979288485889",
      "llm_request_id": null
    }
  ]
}
```

### 行为约束

- 返回顺序与请求 `msg_id_servers` 输入顺序一致
- 即使某个 `msg_id_server` 无匹配记录，也必须返回该项，`llm_request_id=null`
- `llm_request_id` 类型必须是 `string | null`
- `llm_request_id` 指向最终成功并完成 assistant 文本发送的 attempt 日志ID；若未产生绑定消息则返回 `null`

---

## 2) 查询 LLM 请求/响应详情（解析视图）

- **Method / Path**: `POST /admin-api/debug/messages/llm-request-detail`
- **用途**: 根据单个 `llm_request_id` 获取 `ai_request_logs` 详情，并返回可直接展示的解析摘要

### Request

```json
{
  "llm_request_id": "273338979288485888"
}
```

### Response

```json
{
  "detail": {
    "llm_request_id": "273338979288485888",
    "found": true,
    "status": 1,
    "provider_name": "doubao",
    "model_name": "doubao-1.5-pro",
    "response_time_ms": 820,
    "token_count": 1543,
    "created_at": "2026-02-19T08:30:11.123456+00:00",
    "request_preview": "{...}",
    "response_preview": "{...}",
    "summary": {
      "should_reply": true,
      "should_block": false,
      "attack_detected": false,
      "should_update_memory": true,
      "outgoing_messages_count": 1,
      "followup_messages_count": 0,
      "memory_operations_count": 2,
      "score_keys": ["warmth", "trust"],
      "finish_reason": "stop"
    }
  }
}
```

### 行为约束

- `llm_request_id` 输入与输出都必须为字符串
- `request_preview`、`response_preview` 返回完整 JSON 文本（不截断）
- `summary` 是从 `ai_request_logs.response`（含 `response.__min_contract` 诊断信息）解析出的高信号字段，供 Chat Console 快速排障

---

## 3) 查询实例快照（聚合）

- **Method / Path**: `POST /admin-api/debug/instances/snapshot`
- **用途**: 一次性返回实例调试面板所需关键信息（profile/style/personality/relationship/memory）

### Request

至少提供一个定位字段：

- `conversation_id`（推荐）
- 或 `instance_qiao_id`

可选字段：

- `user_qiao_id`（用于严格限定归属账号）

```json
{
  "conversation_id": "conv_abc123",
  "instance_qiao_id": "qiao_ai_001",
  "user_qiao_id": "qiao_user_001"
}
```

### Response

```json
{
  "instance_id": 1001,
  "instance_qiao_id": "qiao_ai_001",
  "persona_id": 2001,
  "contact_username": "xiaoju",
  "user_qiao_id": "qiao_user_001",
  "conversation_id": "conv_abc123",
  "profile": {
    "nickname": "小橘",
    "avatar_url": "https://cdn.example.com/a.webp",
    "bio": "喜欢雨天和旧书",
    "region": "上海",
    "gender": 2
  },
  "style": {
    "id": 12,
    "display_name": "温柔日常"
  },
  "personality": {
    "id": 5,
    "display_name": "细腻陪伴"
  },
  "relationship": {
    "id": 3,
    "display_name": "熟悉朋友",
    "prompt_fragment": "对方是你长期联系的熟悉朋友"
  },
  "memory_items": [
    {
      "memory_type": "preference",
      "importance": 95,
      "content": "用户偏好在晚上聊天，喜欢短句回复。"
    }
  ]
}
```

### 行为约束

- 返回 `persona_id` 与 `contact_username`，用于管理端展示（username 单一真相源）
- `persona_id` 为 `NULL` 表示手动实例（`creation_metadata.source=admin_manual`）
- `contact_username` 当 `persona_id` 存在时为 persona.username，否则为 `null`
- `memory_items` 为摘要视图，条数与内容长度受服务端限制
- 返回内容仅用于管理端联调，不应暴露敏感内部字段
- 若定位目标不存在，返回 `404`

---

## 错误码与错误响应

调试接口失败遵循管理端接口错误响应规范（`detail` + `request_id`），详见：

- `docs/api/error-codes.md`
