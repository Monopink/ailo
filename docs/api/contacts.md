# 联系人服务 API

## 服务信息

- **端口**: 8002
- **基础路径**: `/api/v1/contacts`
- **认证方式**: JWT Bearer Token

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

## 健康检查

### 服务状态检查

```
GET /health
```

**响应**:

```json
{
  "status": "ok"
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

## 更新策略

### 联系人信息更新

1. **点击时更新**: 用户点击联系人时调用chat-info接口获取最新信息
2. **定期更新**: 支持5分钟定期刷新（可通过开关控制）
3. **按需启用**: 通过修改前端`ENABLE_PERIODIC_REFRESH`开关控制
