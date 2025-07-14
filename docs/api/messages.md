# 消息服务 API

## 服务信息

- **端口**: 8003
- **基础路径**: `/api/v1/system`
- **认证方式**: 内部服务密钥 + JWT

## 系统对话管理

### 获取统一系统对话ID

```
GET /api/v1/system/conversation-id
```

**响应**:

```json
{
  "conversation_id": "conv_unified_system_123456"
}
```

### 报告对话错误

```
POST /api/v1/system/conversation-error-report
```

**请求体**:

```json
{
  "error_type": 2,
  "conversation_id": "conv_123456",
  "error_message": "Conversation not found",
  "timestamp": "2024-01-01T00:00:00Z",
  "retry_count": 1,
  "user_agent": "Mozilla/5.0..."
}
```

**响应**:

```json
{
  "status": "received",
  "message": "Error report logged for investigation",
  "report_id": "2024-01-01T00:00:00Z_2"
}
```

## Webhook接口

### LeanCloud消息Webhook

```
POST /webhook/leanmessage
```

**请求体** (由LeanCloud发送):

```json
{
  "fromPeer": "user_entity_id",
  "convId": "conversation_id",
  "msgId": "message_id",
  "content": "用户消息内容",
  "timestamp": 1640995200000
}
```

## 系统消息

系统自动发送状态通知消息给用户，通过LeanCloud统一对话发送。

### 系统消息格式

```json
{
  "id": "system_1752052373681",
  "type": 9,
  "from": "system",
  "to": "qqid_u1002",
  "content": {
    "action": 1,
    "target_message_id": "local_1751776984574_97j85pkjk",
    "status": 3,
    "reason": 6
  },
  "timestamp": "2025-07-09T09:12:53.681Z",
  "service": 1
}
```

### 字段说明

**action** - 系统消息动作类型:

- `1`: MESSAGE_STATUS - 更新消息状态

**status** - 消息状态:

- `3`: FAILED - 消息发送失败
- `4`: BLOCKED - 消息被系统屏蔽
- `5`: DELIVERED - 消息成功送达

**reason** - 失败原因代码:

- `1`: NETWORK_ERROR - 网络连接失败
- `2`: CONVERSATION_ERROR - 对话ID问题
- `3`: BLOCKED_BY_USER - 被用户屏蔽
- `4`: SYSTEM_ERROR - 系统内部错误
- `5`: RATE_LIMITED - 发送频率过快
- `6`: NOT_CONTACTS - 发送方和接收方还不是好友
- `7`: CONTENT_TOO_LONG - 消息内容过长

### 系统消息触发场景

1. **机器人不存在** → status: 3, reason: 6 (NOT_CONTACTS)
2. **用户无权限访问机器人** → status: 3, reason: 6 (NOT_CONTACTS)
3. **机器人状态非活跃** → status: 3, reason: 3 (BLOCKED_BY_USER)
4. **数据库错误** → status: 3, reason: 4 (SYSTEM_ERROR)
5. **其他系统错误** → status: 3, reason: 4 (SYSTEM_ERROR)

## 健康检查

### 服务状态检查

```
GET /health
```

**响应**:

```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T00:00:00Z",
  "conversation_id": "conv_unified_system_123456"
}
```

### 根路径

```
GET /
```

**响应**:

```json
{
  "message": "Welcome to Says API",
  "version": "1.0.0",
  "status": "running"
}
```

## 消息验证规则

### 发送前验证

- 检查发送方和接收方是否为联系人关系
- 验证机器人状态是否为活跃
- 验证消息内容长度和格式
- 检查发送频率限制

### 验证失败处理

验证失败时发送相应的系统消息通知前端，包含具体的失败原因代码。
