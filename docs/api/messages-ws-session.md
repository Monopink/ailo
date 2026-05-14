# WebSocket 会话票据接口

## 接口信息

- **路径**：`POST /api/v1/messages/ws-session`
- **鉴权**：`Authorization: Bearer <access_token>`
- **用途**：签发短时 `ws_ticket`，供 `GET /ws/messages` 首帧 `auth` 使用

## 请求体

```json
{
  "device_id": "uuid"
}
```

约束：

- `device_id` 必须是稳定 UUID（设备/安装级）。

## 成功响应（200）

```json
{
  "config_version": "ws:qiao_user001:0c01f61e-3f76-4b9d-b7d8-7f6d59efceea:1747060000000",
  "session": {
    "client_id": "qiao_user001",
    "provider": "websocket",
    "server_url": "https://synapse.example.com",
    "session_hint": "__ws__",
    "auth": {
      "scheme": "ws_ticket",
      "version": "1",
      "ws_ticket": "<ticket>",
      "issued_at_ms": 1747060000000,
      "device_id": "0c01f61e-3f76-4b9d-b7d8-7f6d59efceea",
      "expires_in_ms": 120000
    }
  },
  "presence": {
    "endpoint_id": 0,
    "lease_ttl_days": 0,
    "lease_expires_at_ms": 0
  }
}
```

`session.server_url` 生成规则：

- 唯一来源：`system_configs.api_base_url`
- 服务端会做规范化：去尾部 `/`
- `prod` 环境：`api_base_url` 必须是 `https://` 绝对地址
- 非 `prod` 环境：允许 `http://` 回环地址（`localhost`、`127.0.0.1`、`::1`），其余仍必须是 `https://` 绝对地址

## 错误响应

- `400 Bad Request`：`device_id` 非法或缺失
- `401 Unauthorized`：登录失效
- `500 Internal Server Error`：系统错误（含 `api_base_url` 缺失或格式非法）
