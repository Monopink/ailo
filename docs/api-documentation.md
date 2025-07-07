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
  "entity_id": "u1001",
  "phone": "13800138002",
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
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
      "entity_id": "b9001",
      "contact_type": 2,
      "nickname": "小爱",
      "bio": "我是一个可爱的AI助手",
      "gender": "female",
      "conversation_id": "conv_123456",
      "last_message_time": "2024-01-01T00:00:00Z"
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
    "entity_id": "u1001",
    "nickname": "用户昵称",
    "bio": "个人简介",
    "gender": "male",
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:00:00Z"
  }
}
```

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

### 认证方式

#### accounts_service
使用配置好的apiClient，自动包含认证头：
```javascript
const response = await apiClient.get('/auth/me')
```

#### contacts_service  
使用原始axios，手动添加认证头：
```javascript
const response = await axios.get('/api/contacts/profile/u1002', {
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  }
})
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
