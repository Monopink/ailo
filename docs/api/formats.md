# 数据格式规范

## Entity ID 设计

### 格式规范

- **格式**: `{prefix}_{type}{number}`
- **默认前缀**: `qqid_`
- **示例**: `qqid_u1001`, `qqid_b9001`

### 类型标识

- `u`: 用户 (User)
- `b`: 机器人 (Bot)
- `s`: 系统 (System)

### 设计原则

- 全局唯一性：所有entity_id在整个系统中唯一
- 字符串类型：API响应中始终使用字符串格式
- 无数据库ID暴露：不暴露数据库自增ID
- 前端映射：前端`id`字段映射到后端`entity_id`

## 消息格式

### 标准消息格式

```json
{
  "type": 1,
  "from": "qqid_b9001",
  "to": "qqid_u1002",
  "content": "消息内容",
  "timestamp": "2025-01-01T00:00:00Z",
  "service": 1
}
```

### 消息类型枚举

- `1`: CHAT - 普通聊天消息
- `2`: TYPING - 输入状态指示
- `9`: SYSTEM - 系统通知消息

### 服务类型枚举

- `1`: 消息服务

## 用户类型

### contact_type 字段

- `1`: 普通用户
- `2`: AI机器人

### 前端术语规范

- 避免使用：'bot', 'entity', 'ai'
- 统一使用：'contact' (联系人)
- 内部标识：'type1', 'type2'

## 错误响应格式

### 标准错误格式

```json
{
  "detail": "用户友好的错误描述"
}
```

### 错误处理原则

- 不暴露内部代码错误
- 不暴露SQL错误信息
- 使用中文用户友好描述
- 开发环境记录详细日志

## 时间格式

### 标准格式

- **格式**: ISO 8601
- **示例**: `2024-01-01T00:00:00Z`
- **时区**: UTC

### 字段命名

- `created_at`: 创建时间
- `updated_at`: 更新时间
- `timestamp`: 消息时间戳
- `last_message_time`: 最后消息时间

## 状态枚举

### 用户状态

- `active`: 活跃
- `inactive`: 非活跃
- `suspended`: 暂停

### 机器人状态

- `active`: 活跃
- `inactive`: 非活跃
- `maintenance`: 维护中

### 消息状态

- `sent`: 已发送
- `delivered`: 已送达
- `failed`: 发送失败
- `blocked`: 被屏蔽

## 性别枚举

### 标准值

- `male`: 男性
- `female`: 女性
- `other`: 其他

### 前端显示

- 使用图标而非文字
- 支持国际化

## 分页格式

### 请求参数

```json
{
  "page": 1,
  "page_size": 20,
  "sort_by": "created_at",
  "sort_order": "desc"
}
```

### 响应格式

```json
{
  "status": "success",
  "data": [...],
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total": 100,
    "total_pages": 5
  }
}
```

## 配置字段

### JSON配置格式

机器人配置使用JSON格式存储：

```json
{
  "friend_config": {...},
  "romance_config": {...},
  "override_config": {...},
  "emotions_config": {...}
}
```

### 配置原则

- 灵活性：支持动态配置
- 可扩展性：便于添加新配置项
- 类型安全：使用Pydantic验证
