# 消息处理流程

## 消息流转架构

### 整体流程

```
用户发送消息 → LeanCloud IM → Webhook → backend
                                              ↓
                                         event_bus (RECEIVED_MESSAGE)
                                              ↓
                                         message.py (统一消息处理中心)
                                              ↓
                                      验证+保存+路由
                                              ↓
                                      model_router.route_message()
                                              ↓
                                        AI模型处理
                                              ↓
                                         响应生成
                                              ↓
                                    message.send_message()
                                              ↓
                                    event_bus (SEND_MESSAGE)
                                              ↓
                                    LeanCloud API发送
```

### 详细步骤

#### 1. 消息接收

```python
# LeanCloud Webhook接收
@app.post("/webhook/leanmessage")
async def leanmessage_webhook(request: Request):
    # 解析LeanCloud消息格式
    # 验证消息来源
    # 转换为内部消息格式
```

#### 2. 统一消息处理

```python
# message.py 作为统一消息处理中心
async def receive_message(message: dict) -> None:
    # 验证消息格式
    # 保存到数据库（消息类型转换为名称存储）
    # 路由到AI模型处理
    await model_router.route_message(message)

async def send_message(
    from_entity: str,
    to_entity: str,
    message_type: str,
    message_service: str,
    content: Optional[Union[str, Dict[str, Any]]] = None,
    message_id: Optional[str] = None,
    **kwargs
) -> None:
    # 基于MessageType枚举自动处理不同类型消息
    # 生成消息ID、验证、发布事件、保存数据库

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
    # 统一系统消息发送逻辑，支持不同类型的系统消息
```

#### 3. 消息路由

```python
# model_router 专注于AI模型管理和路由
class ModelRouter:
    async def route_message(self, message):
        # 验证联系人关系
        # 检查机器人状态
        # 选择AI模型实例
        # 路由到对应处理器
```

#### 4. AI处理

```python
# AI模型处理消息
class AIModel:
    async def receive_message(self, message):
        # 加载上下文历史
        # 调用大模型API
        # 生成个性化回复
        # 更新情感状态
```

#### 5. 响应发送

```python
# AI模型通过统一接口发送消息
await send_message(
    from_entity="qqid_b9001",
    to_entity="qqid_u1001",
    message_type="1",  # MessageType.CHAT.code
    message_service="leancloud",
    content="AI回复内容"
)

# 发送系统消息示例
await send_system_message(
    from_entity="qqid_abc123",
    to_entity="qqid_abc456",
    action=SystemMessageAction.MESSAGE_STATUS,
    target_message_id="local_1751776984574_97j85pkjk",
    status=SystemMessageStatus.FAILED,
    reason=SystemMessageReason.NOT_CONTACTS
)
```

## 统一消息处理架构

### 核心设计原则

1. **message.py 作为统一消息处理中心**
   - 所有消息收发都经过message.py处理
   - 基于MessageType枚举自动处理不同类型消息
   - 统一的验证、保存、ID生成逻辑

2. **model_router 专注于AI模型管理**
   - 移除消息处理职责
   - 专注于模型实例管理和消息路由
   - 提供公共route_message()方法

3. **事件驱动架构保持完整**
   - 接收：RECEIVED_MESSAGE事件
   - 发送：SEND_MESSAGE事件
   - 保持系统解耦和扩展性

### 消息类型处理

```python
# 前端发送数字类型
message_type: "1"  # chat
message_type: "2"  # typing
message_type: "9"  # system

# 数据库存储名称类型
message_type: "chat"
message_type: "typing"
message_type: "system"
```

## 消息验证机制

### 发送前验证

```python
async def validate_message(self, message):
    # 1. 检查联系人关系
    if not await self.check_contact_relationship(from_id, to_id):
        return False, "NOT_CONTACTS"
    
    # 2. 验证机器人状态  
    if not await self.check_bot_active(bot_id):
        return False, "BLOCKED_BY_USER"
        
    # 3. 内容长度检查
    if len(message.content) > MAX_MESSAGE_LENGTH:
        return False, "CONTENT_TOO_LONG"
        
    return True, None
```

### 验证失败处理

```python
# 发送系统消息通知失败
await send_system_message(
    from_entity=bot_id,
    to_entity=user_id,
    action=SystemMessageAction.MESSAGE_STATUS,
    target_message_id=message_id_client,
    status=SystemMessageStatus.FAILED,
    reason=failure_reason
)
```

## 系统消息机制

### 系统消息类型

- **状态更新**: 通知消息发送状态变化
- **错误报告**: 通知发送失败原因
- **系统通知**: 机器人状态变更通知

### 系统消息格式

```json
{
  "id": "system_1752052373681",
  "type": 9,
  "from": "qqid_b9001",
  "to": "qqid_u1001",
  "content": {
    "action": 1,
    "target_message_id": "local_1751776984574_97j85pkjk",
    "status": 3,
    "reason": 6,
    "message": "您还不是该联系人的好友，无法发送消息"
  },
  "timestamp": "2025-07-09T09:12:53.681Z",
  "service": 1
}
```

**content 字段说明**:

- `action`: 系统消息动作类型（1=MESSAGE_STATUS, 2=NEW_CONTACT）
- `target_message_id`: 目标消息ID（仅用于MESSAGE_STATUS）
- `status`: 消息状态（仅用于MESSAGE_STATUS）
- `reason`: 失败原因代码（仅用于MESSAGE_STATUS）
- `contact_id`: 联系人ID（仅用于NEW_CONTACT）
- `message`: **可选的自定义消息文本**，包含在content中，用于覆盖前端默认的错误消息显示

### 触发场景

1. **机器人不存在** → NOT_CONTACTS
2. **无联系人关系** → NOT_CONTACTS  
3. **机器人非活跃** → BLOCKED_BY_USER
4. **系统内部错误** → SYSTEM_ERROR
5. **内容过长** → CONTENT_TOO_LONG

## LeanCloud集成

### 统一系统对话

- 所有机器人消息使用单一conversation_id
- 优先保证消息送达，而非ID新鲜度
- 系统对话由backend管理

### Webhook配置

```python
# 只有系统对话触发webhook
webhook_url = "https://your-domain.com/webhook/leanmessage"
conversation_type = "system"
```

### 消息加密

- 消息内容在LeanCloud传输前加密
- 加密由提供者层处理，非消息服务层
- 保持结构化消息格式

## 错误处理与重试

### 消息失败处理

```python
# 消息发送失败时
try:
    await send_to_leancloud(message)
except LeanCloudError as e:
    # 记录错误日志
    logger.error("message_send_failed", error=str(e))
    
    # 发送系统消息通知前端
    await send_system_message(
        from_entity=bot_id,
        to_entity=user_id,
        action=SystemMessageAction.MESSAGE_STATUS,
        target_message_id=message_id_client,
        status=SystemMessageStatus.FAILED,
        reason=SystemMessageReason.NETWORK_ERROR
    )
```

### 重试机制

- 前端显示失败消息，支持用户手动重试
- 不实现自动重试，避免消息重复
- 系统消息提供详细失败原因

## 性能优化

### 消息路由优化

- 复用AI模型实例，避免重复初始化
- 异步处理，提高并发能力
- 连接池管理数据库连接

### 内存管理

- 限制消息历史加载数量
- 定期清理不活跃的模型实例
- 优化事件总线内存使用

### 监控指标

- 消息处理延迟
- AI模型响应时间
- 系统消息发送成功率
- 错误类型分布统计
