# Says AI 聊天交友软件 API 文档

## 项目概述

这是一个基于微服务架构的AI聊天交友软件的完整API文档。系统包含三个主要后端服务和一个前端应用。

## 服务架构

- **accounts_service** (端口 8001): 用户账号管理和认证
- **contacts_service** (端口 8002): 联系人和机器人信息管理  
- **bot_message_service** (端口 8003): 消息处理和AI响应
- **frontend** (端口 5173): Vue.js前端应用

## 1. accounts_service API (端口 8001)

### 基础路径: `/api/v1`

#### 认证相关 (`/auth`)

##### POST `/api/v1/auth/send-code`

发送短信验证码

**请求体:**

```json
{
  "phone": "13800138002"
}
```

**响应:**

```json
{
  "msg": "SMS code sent successfully."
}
```

##### POST `/api/v1/auth/register`

用户注册

**请求体:**

```json
{
  "phone": "13800138002",
  "code": "123456",
  "password": "12345678"
}
```

**响应:**

```json
{
  "entity_id": "u1001",
  "phone": "13800138002",
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

##### POST `/api/v1/auth/login/password`

密码登录

**请求体:**

```json
{
  "phone": "13800138002",
  "password": "12345678"
}
```

**响应:**

```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer"
}
```

##### POST `/api/v1/auth/login/code`

验证码登录

**请求体:**

```json
{
  "phone": "13800138002",
  "code": "123456"
}
```

**响应:**

```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer"
}
```

##### POST `/api/v1/auth/reset-password`

重置密码

**请求体:**

```json
{
  "phone": "13800138002",
  "code": "123456",
  "new_password": "newpassword123"
}
```

**响应:**

```json
{
  "msg": "Password updated successfully."
}
```

#### 用户相关 (`/users`)

##### GET `/api/v1/users/me`

获取当前用户信息 (需要认证)

**请求头:**

```
Authorization: Bearer <token>
```

**响应:**

```json
{
  "id": "u1001",
  "phone": "13800138002",
  "username": null,
  "email": null,
  "status": "active",
  "role": "user",
  "is_verified": true,
  "subscription_type": "free"
}
```

#### 健康检查

##### GET `/health`

服务健康检查

**响应:**

```json
{
  "status": "ok",
  "service": "accounts_service"
}
```

## 2. contacts_service API (端口 8002)

### 基础路径: `/api/v1`

#### 联系人相关 (`/contacts`)

##### GET `/api/v1/contacts`

获取用户联系人列表 (需要认证)

**请求头:**

```
Authorization: Bearer <token>
```

**响应:**

```json
{
  "status": "success",
  "data": [
    {
      "id": "b9001",
      "contact_type": 2,
      "nickname": "小海",
      "avatar_url": null
    }
  ]
}
```

##### GET `/api/v1/contacts/{contact_entity_id}`

获取特定联系人信息 (需要认证)

**请求头:**

```
Authorization: Bearer <token>
```

**响应:**

```json
{
  "status": "success",
  "data": {
    "entity_id": "b9001",
    "contact_type": 2,
    "nickname": "小爱",
    "bio": "我是一个可爱的AI助手",
    "gender": "female",
    "conversation_id": "conv_123456",
    "last_message_time": "2024-01-01T00:00:00Z"
  }
}
```

##### GET `/api/v1/contacts/profile/{entity_id}`

获取社交档案信息 (需要认证)

**请求头:**

```
Authorization: Bearer <token>
```

**响应:**

```json
{
  "status": "success",
  "data": {
    "id": "u1001",
    "nickname": "用户昵称",
    "bio": "个人简介",
    "avatar_url": null,
    "birth_date": "1995-06-15",
    "location": "北京市"
  }
}
```

##### GET `/api/v1/contacts/{contact_entity_id}/chat-info`

获取联系人对话列表信息 (需要认证)

**描述**: 获取指定联系人的对话列表显示信息（轻量级接口，用于对话列表显示和实时更新）

**请求头:**

```
Authorization: Bearer <token>
```

**路径参数:**

- `contact_entity_id`: 联系人实体ID

**响应:**

```json
{
  "status": "success",
  "data": {
    "id": "u1001",
    "nickname": "用户昵称",
    "avatar_url": "https://example.com/avatar.jpg",
    "last_updated": "2024-01-15T10:30:00Z"
  }
}
```

**字段说明:**

- `id`: 联系人ID (对应前端chat.id)
- `nickname`: 显示昵称
- `avatar_url`: 头像URL (预留字段，前端暂不显示)
- `last_updated`: 资料最后更新时间 (ISO 8601格式)

**使用场景:**

此接口是为了解决用户资料更新后，其他用户的对话列表显示不及时更新的问题而设计的轻量级接口。

**更新策略:**

1. **点击时更新**: 用户点击特定联系人开始对话时，前端会调用此接口获取该联系人的最新显示信息
2. **定期更新**: 前端具备5分钟定期刷新全部联系人的机制，但目前通过功能开关设置为关闭状态
3. **按需启用**: 当系统需要更频繁的数据同步时，可以通过修改前端代码中的`ENABLE_PERIODIC_REFRESH`开关来启用定期更新功能

**性能优化:**

- 相比完整的联系人接口，此接口只返回对话列表必需的显示字段，减少网络传输
- 支持单个联系人精准更新，避免不必要的全量数据获取

#### 健康检查

##### GET `/health`

服务健康检查

**响应:**

```json
{
  "status": "ok"
}
```

## 3. bot_message_service API (端口 8003)

### 基础路径: `/api/v1/system`

#### 系统相关 (`/system`)

##### GET `/api/v1/system/conversation-id`

获取统一系统对话ID

**响应:**

```json
{
  "conversation_id": "conv_unified_system_123456"
}
```

##### POST `/api/v1/system/conversation-error-report`

报告对话ID错误

**请求体:**

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

**响应:**

```json
{
  "status": "received",
  "message": "Error report logged for investigation",
  "report_id": "2024-01-01T00:00:00Z_2"
}
```

#### 系统消息

系统会自动发送系统消息来通知前端消息发送状态变化。系统消息通过LeanCloud统一对话发送给用户。

##### 系统消息格式

```json
{
  "id": "system_1752052373681",
  "type": 9,
  "from": "system",
  "to": "u1002",
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

##### 系统消息字段说明

- **action**: 系统消息动作类型 (数字)
  - `1`: MESSAGE_STATUS - 更新消息状态
- **target_message_id**: 目标消息的客户端ID (对应前端发送消息的id字段)
- **status**: 消息状态 (数字，对应前端MessageStatus枚举)
  - `3`: FAILED - 消息发送失败
  - `4`: BLOCKED - 消息被系统屏蔽
  - `5`: DELIVERED - 消息成功送达
- **reason**: 失败原因代码 (数字，对应前端MessageFailureReason枚举)
  - `1`: NETWORK_ERROR - 网络连接失败
  - `2`: CONVERSATION_ERROR - 对话ID问题
  - `3`: BLOCKED_BY_USER - 被用户屏蔽
  - `4`: SYSTEM_ERROR - 系统内部错误
  - `5`: RATE_LIMITED - 发送频率过快
  - `6`: NOT_CONTACTS - 发送方和接收方还不是好友
  - `7`: CONTENT_TOO_LONG - 消息内容过长

##### 系统消息触发场景

1. **机器人不存在** → status: 3, reason: 6 (NOT_CONTACTS)
2. **用户无权限访问机器人** → status: 3, reason: 6 (NOT_CONTACTS)
3. **机器人状态非活跃** → status: 3, reason: 3 (BLOCKED_BY_USER)
4. **数据库错误** → status: 3, reason: 4 (SYSTEM_ERROR)
5. **其他系统错误** → status: 3, reason: 4 (SYSTEM_ERROR)

#### Webhook端点

##### POST `/webhook/leanmessage`

LeanCloud消息Webhook

**请求体:** (由LeanCloud发送)

```json
{
  "fromPeer": "user_entity_id",
  "convId": "conversation_id",
  "msgId": "message_id",
  "content": "用户消息内容",
  "timestamp": 1640995200000
}
```

#### 健康检查

##### GET `/health`

服务健康检查

**响应:**

```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T00:00:00Z",
  "conversation_id": "conv_unified_system_123456"
}
```

##### GET `/`

根路径

**响应:**

```json
{
  "message": "Welcome to Says API",
  "version": "1.0.0",
  "status": "running"
}
```

## 前端API调用模式

### Vite代理配置

前端通过Vite代理将请求路由到不同的后端服务：

- `/api/v1/system/*` → bot_message_service:8000
- `/api/v1/*` → accounts_service:8000
- `/api/contacts/*` → contacts_service:8000 (重写为 `/api/v1/contacts/*`)

### 统一API调用方式

前端已重构为使用统一的 `apiClient`，自动处理认证和日志记录：

```javascript
import { apiClient } from '../utils/apiHelpers';

// 所有API调用都使用相同的模式
const response = await apiClient.get('/auth/me');
const response = await apiClient.post('/auth/login', { phone, password });
const response = await apiClient.get('/contacts');
const response = await apiClient.post('/contacts/add', { contact_id });
```

### 错误处理

使用统一的错误处理，支持业务操作提示：

```javascript
import { handleApiError } from '../utils/errorHandler';

try {
  const response = await apiClient.post('/auth/login', data);
} catch (error) {
  // 自动显示后端返回的用户友好消息，或使用操作特定的消息
  handleApiError(error, 'login');
}
```

## 错误处理

### 标准错误响应格式

```json
{
  "detail": "错误描述信息"
}
```

### 常见HTTP状态码

- `200`: 成功
- `400`: 请求参数错误
- `401`: 未认证或认证失败
- `404`: 资源不存在
- `500`: 服务器内部错误

## 数据安全说明

1. **无数据库ID暴露**: 所有API响应都使用entity_id，不暴露数据库自增ID
2. **JWT认证**: 使用Bearer Token进行API认证
3. **CORS配置**: 严格的跨域资源共享配置
4. **输入验证**: 所有输入都经过严格验证和清理

## 测试账号

- **手机号**: 13800138002
- **密码**: 12345678
- **验证码**: 任意6位数字（开发环境）
