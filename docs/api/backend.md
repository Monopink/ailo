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

## LeanCloud消息服务管理

### 获取LeanCloud系统对话ID

```
GET /api/v1/client/leancloud-conversation-id
```

**说明**: 获取用于所有机器人对话的LeanCloud系统对话ID。如果不存在会自动创建。

**认证**: 需要JWT认证

**响应**:

```json
{
  "conversation_id": "conv_unified_system_123456"
}
```

### LeanCloud消息服务健康检查

```
GET /api/v1/client/health/leancloud-message-service
```

**说明**: 检查LeanCloud消息服务的健康状态，用于监控。

**认证**: 不需要认证

**响应**:

```json
{
  "leancloud_message_service": "healthy",
  "leancloud_api": "healthy",
  "leancloud_conversation_id": "healthy",
  "details": {}
}
```

**状态值**:

- `healthy`: 服务正常
- `unhealthy`: 服务异常但可恢复
- `error`: 服务错误

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
  "leancloud_message_service": {
    "leancloud_message_service": "healthy",
    "leancloud_api": "healthy",
    "leancloud_conversation_id": "healthy",
    "details": {}
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

## 数据库访问模式

### 统一数据库访问架构

后端实现了基于依赖注入和分层架构原则的统一数据库访问模式。

#### API层模式

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from api.deps import get_db, get_current_user

@router.get("/contacts")
async def get_contacts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """通过依赖注入获取用户联系人"""
    contact_list = await get_user_contacts(db, current_user.entity_id)
    return {"status": "success", "data": contact_list}
```

#### 服务层模式

```python
from sqlalchemy.ext.asyncio import AsyncSession

async def get_user_contacts(session: AsyncSession, user_entity_id: str):
    """接收注入session的服务函数"""
    contacts_result = await session.execute(
        select(Contact).where(Contact.user_entity_id == user_entity_id)
    )
    return [contact.to_dict() for contact in contacts_result.scalars().all()]
```

#### 核心原则

- **API层**：使用FastAPI依赖注入（`Depends(get_db)`）
- **服务层**：接收`AsyncSession`参数，从不创建自己的连接
- **事务控制**：API层管理事务边界
- **类型安全**：所有函数使用正确的`AsyncSession`类型注解

## 消息发送API

### 统一消息发送接口

```python
async def send_message(
    from_entity: str,
    to_entity: str,
    message_type: str,
    message_service: str,
    content: Optional[Union[str, Dict[str, Any]]] = None,
    message_id: Optional[str] = None,
    **kwargs
) -> None:
```

**参数说明**:

- `from_entity`: 发送方实体ID
- `to_entity`: 接收方实体ID
- `message_type`: 消息类型代码（字符串）
- `message_service`: 服务类型
- `content`: 消息内容（聊天消息为字符串，系统消息为字典）
- `message_id`: 可选的消息ID
- `**kwargs`: 扩展字段

### 系统消息发送接口

```python
async def send_system_message(
    from_entity: str,
    to_entity: str,
    action: SystemMessageAction,
    target_message_id: Optional[str] = None,
    status: Optional[SystemMessageStatus] = None,
    reason: Optional[SystemMessageReason] = None,
    contact_id: Optional[str] = None,
    custom_message: Optional[str] = None,
) -> None:
```

**参数说明**:

- `from_entity`: 源实体ID（用于聊天窗口识别）
- `to_entity`: 目标实体ID
- `action`: 系统消息动作类型
- `target_message_id`: 客户端消息ID（用于MESSAGE_STATUS）
- `status`: 系统消息状态（用于MESSAGE_STATUS）
- `reason`: 失败原因代码（用于MESSAGE_STATUS）
- `contact_id`: 联系人实体ID（用于NEW_CONTACT）
- `custom_message`: 可选的自定义消息文本（会作为 `content.message` 字段发送给前端，用于覆盖默认错误消息）

### 使用示例

#### 发送聊天消息

```python
await send_message(
    from_entity="qqid_b9001",
    to_entity="qqid_u1001",
    message_type="1",  # MessageType.CHAT.code
    message_service="leancloud",
    content="Hello, world!"
)
```

#### 发送系统状态消息

```python
# 使用默认错误消息
await send_system_message(
    from_entity="qqid_b9001",
    to_entity="qqid_u1001",
    action=SystemMessageAction.MESSAGE_STATUS,
    target_message_id="local_1751776984574_97j85pkjk",
    status=SystemMessageStatus.FAILED,
    reason=SystemMessageReason.NOT_CONTACTS
)

# 使用自定义错误消息
await send_system_message(
    from_entity="qqid_b9001",
    to_entity="qqid_u1001",
    action=SystemMessageAction.MESSAGE_STATUS,
    target_message_id="local_1751776984574_97j85pkjk",
    status=SystemMessageStatus.FAILED,
    reason=SystemMessageReason.NOT_CONTACTS,
    custom_message="您还不是该联系人的好友，无法发送消息"
)
```

#### 发送新联系人通知

```python
await send_system_message(
    from_entity="qqid_b9001",
    to_entity="qqid_u1001",
    action=SystemMessageAction.NEW_CONTACT,
    contact_id="qqid_b9001"
)
```
