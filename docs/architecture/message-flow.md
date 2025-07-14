# 消息处理流程

## 消息流转架构

### 整体流程

```
用户发送消息 → LeanCloud IM → Webhook → bot_message_service
                                              ↓
                                         event_bus
                                              ↓
                                      message_router
                                              ↓
                                        AI模型处理
                                              ↓
                                         响应生成
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

#### 2. 事件发布

```python
# 发布到事件总线
event_bus.publish("message_received", {
    "from": "qqid_u1001",
    "to": "qqid_b9001", 
    "content": "用户消息内容",
    "timestamp": "2024-01-01T00:00:00Z"
})
```

#### 3. 消息路由

```python
# 消息路由器处理
class MessageRouter:
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
# 通过LeanCloud发送回复
await leancloud_client.send_message(
    conversation_id="conv_123456",
    content="AI回复内容",
    from_peer="qqid_b9001"
)
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
await self.send_system_message(
    from_bot=bot_id,
    to_user=user_id,
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
- 系统对话由contacts_service管理

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
