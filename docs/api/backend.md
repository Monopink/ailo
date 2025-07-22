# Backend API

## 服务信息

- **端口**: 8000
- **基础路径**: `/api/v1`
- **认证方式**: JWT Bearer Token

## 认证接口

### 发送短信验证码

```
POST /api/v1/auth/send-code
```

**请求体**:

```json
{
  "phone": "13800138002"
}
```

**响应**:

```json
{
  "msg": "SMS code sent successfully."
}
```

### 用户注册

```
POST /api/v1/auth/register
```

**请求体**:

```json
{
  "phone": "13800138002",
  "code": "123456",
  "password": "12345678"
}
```

**响应**:

```json
{
  "entity_id": "qqid_u1001",
  "phone": "13800138002",
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

### 密码登录

```
POST /api/v1/auth/login/password
```

**请求体**:

```json
{
  "phone": "13800138002",
  "password": "12345678"
}
```

**响应**:

```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer"
}
```

### 验证码登录

```
POST /api/v1/auth/login/code
```

**请求体**:

```json
{
  "phone": "13800138002",
  "code": "123456"
}
```

**响应**:

```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer"
}
```

### 重置密码

```
POST /api/v1/auth/reset-password
```

**请求体**:

```json
{
  "phone": "13800138002",
  "code": "123456",
  "new_password": "newpassword123"
}
```

**响应**:

```json
{
  "msg": "Password updated successfully."
}
```

## 用户信息接口

### 获取当前用户信息

```
GET /api/v1/users/me
```

**请求头**:

```
Authorization: Bearer <token>
```

**响应**:

```json
{
  "id": "qqid_u1001",
  "phone": "13800138002",
  "username": null,
  "email": null,
  "status": "active",
  "role": "user",
  "is_verified": true,
  "subscription_type": "free"
}
```

## 联系人管理

### 获取联系人列表

```
GET /api/v1/contacts
```

**请求头**:

```
Authorization: Bearer <token>
```

**响应**:

```json
{
  "status": "success",
  "data": [
    {
      "id": "qqid_b9001",
      "contact_type": 2,
      "nickname": "小海",
      "avatar_url": null
    }
  ]
}
```

### 获取联系人详细信息

```
GET /api/v1/contacts/{contact_entity_id}
```

**请求头**:

```
Authorization: Bearer <token>
```

**响应**:

```json
{
  "status": "success",
  "data": {
    "entity_id": "qqid_b9001",
    "contact_type": 2,
    "nickname": "小爱",
    "bio": "我是一个可爱的AI助手",
    "gender": "female",
    "conversation_id": "conv_123456",
    "last_message_time": "2024-01-01T00:00:00Z"
  }
}
```

### 获取联系人聊天信息

```
GET /api/v1/contacts/{contact_entity_id}/chat-info
```

**用途**: 轻量级接口，用于对话列表显示和实时更新

**请求头**:

```
Authorization: Bearer <token>
```

**响应**:

```json
{
  "status": "success",
  "data": {
    "id": "qqid_u1001",
    "nickname": "用户昵称",
    "avatar_url": "https://example.com/avatar.jpg",
    "last_updated": "2024-01-15T10:30:00Z"
  }
}
```

**字段说明**:

- `id`: 联系人ID (对应前端chat.id)
- `nickname`: 显示昵称
- `avatar_url`: 头像URL
- `last_updated`: 资料最后更新时间

## 社交档案管理

### 获取社交档案

```
GET /api/v1/contacts/profile/{entity_id}
```

**请求头**:

```
Authorization: Bearer <token>
```

**响应**:

```json
{
  "status": "success",
  "data": {
    "id": "qqid_u1001",
    "nickname": "用户昵称",
    "bio": "个人简介",
    "avatar_url": null,
    "birth_date": "1995-06-15",
    "location": "北京市"
  }
}
```

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
  "database": "connected",
  "event_bus": "running",
  "leancloud_conversation": {
    "health": "healthy",
    "metrics": {}
  }
}
```

## 数据字段说明

### contact_type 联系人类型

- `1`: 普通用户
- `2`: AI机器人

### 前端映射规则

- 前端 `id` 字段映射到后端 `entity_id`
- 所有entity_id使用字符串格式，带有可配置前缀（默认：'qqid_'）
- 前端避免使用 'bot', 'entity', 'ai' 等术语，统一使用 'contact'

## 消息验证规则

### 发送前验证

- 检查发送方和接收方是否为联系人关系
- 验证机器人状态是否为活跃
- 验证消息内容长度和格式
- 检查发送频率限制

### 验证失败处理

验证失败时发送相应的系统消息通知前端，包含具体的失败原因代码。

## 错误响应格式

所有错误响应统一格式：

```json
{
  "detail": "错误描述信息"
}
```

## HTTP状态码

- `200`: 成功
- `400`: 请求参数错误
- `401`: 未认证或认证失败
- `404`: 资源不存在
- `500`: 服务器内部错误
