# 账号服务 API

## 服务信息

- **端口**: 8001
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

## 健康检查

### 服务状态检查

```
GET /health
```

**响应**:

```json
{
  "status": "ok",
  "service": "accounts_service"
}
```

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
