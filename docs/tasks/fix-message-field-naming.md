# Task: 修复消息字段命名不一致问题

**日期**: 2026-01-19
**状态**: 待实施
**优先级**: 高（阻塞性 bug）

---

## 问题描述

### 问题1: 发送消息报错
小程序主动发送消息时报错：
```
Cannot set property status of #<e> which has only a getter
```

**错误位置**: `frontend/wx-minipg/utils/message/leancloud.ts:87`

### 问题2: 未收到系统消息
添加联系人后，用户没有收到「对方已经添加你为联系人」的 chat-info 消息。

---

## 根本原因分析

### 原因1: BusinessMessage 构造函数问题

**文件**: `frontend/wx-minipg/utils/message/leancloud.ts:85-88`

```typescript
constructor(data: Partial<BusinessMessagePayload> = {}) {
  super();
  Object.assign(this, data);  // ❌ 尝试设置只读属性 status
}
```

- `BusinessMessage` 继承自 LeanCloud 的 `TypedMessage`
- `TypedMessage.status` 是只读的 getter 属性
- `Object.assign` 尝试设置 `status` 导致错误

**已修复**: ✅ 已在第一次修改中解决

### 原因2: 前后端字段名不一致 ⚠️

**后端发送的字段** (`backend/app/services/message/providers/leancloud/adapter.py:235-244`):
```python
attrs = {
    "msg_id": msg_id,
    "from_qiao_id": from_qiao_id,      # 后端使用 from_qiao_id
    "to_qiao_id": to_qiao_id,          # 后端使用 to_qiao_id
    "conv_id": conv_id,
    "content": content,
    "message_type": message_type,
    "supports_typing": supports_typing,
    "sent_time": int(time.time() * 1000),
}
```

**前端期望的字段** (`frontend/wx-minipg/utils/message/leancloud.ts:74-76, 92-105`):
```typescript
class BusinessMessage extends TypedMessage {
  from = '';  // ❌ 前端期望 from
  to = '';    // ❌ 前端期望 to
  // ...
}

messageField([
  'msg_id',
  'from',        // ❌ 前端注册 from
  'to',          // ❌ 前端注册 to
  'conv_id',
  // ...
])(BusinessMessage);
```

**结果**:
1. 后端发送的消息到达 LeanCloud
2. 前端收到消息后，LeanCloud SDK 无法将消息反序列化为 `BusinessMessage` 实例（字段名不匹配）
3. `handleMessage` 中的 `instanceof BusinessMessage` 检查失败
4. 消息被忽略，记录为 "Received non-business message"

**证据**:
```
后端日志:
event=leancloud_message_sent
from_client=system
to_clients=qiao_T1HcpPKmgrST23zH
msg_id=9jvgOemYc897xAPX9JhQGe

前端日志:
logger.warn('Received non-business message', { type: nonBusinessType });
```

---

## 架构分析与决策

### 方案对比

| 方案 | 优点 | 缺点 |
|------|------|------|
| **方案1: 后端改为 `from`/`to`** | 简洁 | - 语义不明确<br>- 与系统其他地方不一致<br>- 可扩展性差 |
| **方案2: 前端改为 `from_qiao_id`/`to_qiao_id`** ✅ | - 语义明确<br>- 系统一致性<br>- 可扩展性好<br>- 符合 DDD 原则 | 需要修改前端多处代码 |

### 最终决策：采用方案2

**理由**:

1. **领域驱动设计（DDD）**: `qiao_id` 是系统核心业务概念，应在所有层保持统一语言
2. **语义明确性**: `from_qiao_id` 明确表达字段含义，避免歧义
3. **可扩展性**: 为未来可能的多标识符场景（`from_user_id`, `from_external_id`）留出空间
4. **前后端契约**: 后端是消息格式的权威定义，前端应遵循
5. **类型安全**: 提高 TypeScript 的自文档化能力
6. **行业最佳实践**: 主流系统（Slack, Discord, WeChat）都使用明确的标识符命名

---

## 实施方案

### 第一步: 修改 BusinessMessage 类定义

**文件**: `frontend/wx-minipg/utils/message/leancloud.ts`

```typescript
class BusinessMessage extends TypedMessage {
  id?: string;
  timestamp?: number;
  msg_id = '';
  from_qiao_id = '';        // ✅ 改为 from_qiao_id
  to_qiao_id = '';          // ✅ 改为 to_qiao_id
  conv_id = '';
  content = '';
  message_type: MessageType = MESSAGE_TYPE.TEXT;
  supports_typing = true;
  sent_time = 0;
  action: string | null = null;
  notification_type: string | null = null;
  data: Record<string, unknown> | null = null;

  constructor(data: Partial<BusinessMessagePayload> = {}) {
    super();
    // 已修复：避免设置只读属性
    if (data.msg_id !== undefined) this.msg_id = data.msg_id;
    if (data.from_qiao_id !== undefined) this.from_qiao_id = data.from_qiao_id;
    if (data.to_qiao_id !== undefined) this.to_qiao_id = data.to_qiao_id;
    if (data.conv_id !== undefined) this.conv_id = data.conv_id;
    if (data.content !== undefined) this.content = data.content;
    if (data.message_type !== undefined) this.message_type = data.message_type;
    if (data.supports_typing !== undefined) this.supports_typing = data.supports_typing;
    if (data.sent_time !== undefined) this.sent_time = data.sent_time;
    if (data.action !== undefined) this.action = data.action;
    if (data.notification_type !== undefined) this.notification_type = data.notification_type;
    if (data.data !== undefined) this.data = data.data;
  }
}

// 声明 LeanCloud 消息字段
messageField([
  'msg_id',
  'from_qiao_id',          // ✅ 改为 from_qiao_id
  'to_qiao_id',            // ✅ 改为 to_qiao_id
  'conv_id',
  'content',
  'message_type',
  'supports_typing',
  'sent_time',
  'action',
  'notification_type',
  'data',
])(BusinessMessage);
```

### 第二步: 修改类型定义

**文件**: `frontend/wx-minipg/utils/message/adapter-types.ts`

需要检查并更新以下类型定义：
- `BusinessMessagePayload`
- `AdapterMessage`
- 任何使用 `from` / `to` 字段的接口

### 第三步: 修改 processBusinessMessage 方法

**文件**: `frontend/wx-minipg/utils/message/leancloud.ts:427-463`

```typescript
private processBusinessMessage(message: BusinessMessage): void {
  const lcMsgId = typeof message.id === 'string' && message.id !== '' ? message.id : message.msg_id;
  const lcTimestamp =
    typeof message.timestamp === 'number' && Number.isFinite(message.timestamp)
      ? message.timestamp
      : Date.now();

  const businessData: AdapterMessage = {
    msg_id: message.msg_id,
    from: message.from_qiao_id,        // ✅ 使用 from_qiao_id
    to: message.to_qiao_id,            // ✅ 使用 to_qiao_id
    conv_id: message.conv_id,
    content: message.content,
    message_type: message.message_type,
    supports_typing: message.supports_typing,
    sent_time: message.sent_time,
    status: MESSAGE_STATUS.RECEIVED,
    lc_msg_id: lcMsgId,
    lc_timestamp: lcTimestamp,
    action: message.action ?? null,
    notification_type: message.notification_type ?? null,
    data: message.data ?? null,
  };

  // ... 其余代码
}
```

### 第四步: 搜索并修改所有使用处

**搜索范围**: `frontend/wx-minipg/**/*.{ts,js}`

**搜索模式**:
```bash
# 搜索 message.from 或 msg.from
grep -r "message\.from\b" frontend/wx-minipg/
grep -r "msg\.from\b" frontend/wx-minipg/

# 搜索 message.to 或 msg.to
grep -r "message\.to\b" frontend/wx-minipg/
grep -r "msg\.to\b" frontend/wx-minipg/
```

**需要检查的文件**:
- `utils/message/service.ts`
- `utils/message/message-view-model.ts`
- `utils/message/message-state-store.ts`
- 所有聊天相关的页面组件
- 所有使用消息对象的工具函数

### 第五步: 更新 MessageService 层

**文件**: `frontend/wx-minipg/utils/message/service.ts`

检查 `buildIncomingPayload` 和其他使用消息字段的方法。

---

## 测试验证

### 测试场景1: 发送消息
- [ ] 用户发送文本消息
- [ ] 用户发送图片消息
- [ ] 验证消息发送成功，无报错

### 测试场景2: 接收消息
- [ ] 接收普通文本消息
- [ ] 接收系统消息（CHAT_INFO）
- [ ] 验证消息正确显示在聊天界面

### 测试场景3: 添加联系人
- [ ] 在广场页面添加 AI 联系人
- [ ] 验证联系人出现在聊天列表
- [ ] **验证收到「对方已经添加你为联系人」的系统消息** ⚠️

### 测试场景4: 消息字段完整性
- [ ] 验证 `from_qiao_id` 正确解析
- [ ] 验证 `to_qiao_id` 正确解析
- [ ] 验证其他字段（content, message_type 等）正确解析

---

## 风险评估

### 高风险点
1. **字段名遗漏**: 可能有些地方使用了 `from`/`to` 但未被搜索到
2. **类型定义不一致**: TypeScript 类型定义可能与实际代码不一致

### 缓解措施
1. 使用 TypeScript 编译器检查：`npm run type-check`
2. 使用 ESLint 检查：`npm run lint`
3. 全面的手动测试

---

## 预期影响

### 修改文件列表
- `frontend/wx-minipg/utils/message/leancloud.ts` ✅ 部分已修改
- `frontend/wx-minipg/utils/message/adapter-types.ts`
- `frontend/wx-minipg/utils/message/service.ts`
- `frontend/wx-minipg/utils/message/message-view-model.ts`
- 其他使用消息字段的文件（待搜索确认）

### 代码行数
预计修改 20-50 行代码

### 测试工作量
预计需要 2-3 小时完整测试

---

## 参考资料

### 相关代码位置

**后端**:
- 消息构造: `backend/app/services/message/providers/leancloud/adapter.py:204-257`
- 发送系统消息: `backend/app/services/message/providers/leancloud/service.py:512-587`
- 添加联系人后发送消息: `backend/app/services/contact/request_service.py:319-328`

**前端**:
- BusinessMessage 定义: `frontend/wx-minipg/utils/message/leancloud.ts:70-108`
- 消息处理: `frontend/wx-minipg/utils/message/leancloud.ts:427-494`
- 消息服务: `frontend/wx-minipg/utils/message/service.ts:262-288`

### 日志示例

**成功的后端日志**:
```
event=leancloud_message_sent
conversation_id=695cf55d722720749efad3a5
from_client=system
to_clients=qiao_T1HcpPKmgrST23zH
msg_id=9jvgOemYc897xAPX9JhQGe
```

**预期的前端日志**（修复后）:
```
[MessageService] Message received
  msg_id: xxx
  from: system
  to: qiao_T1HcpPKmgrST23zH
  message_type: 4 (CHAT_INFO)
```

---

## 后续优化建议

1. **类型定义统一**: 考虑使用共享的 TypeScript 类型定义（如通过 OpenAPI 生成）
2. **消息格式文档**: 创建消息格式的正式文档
3. **端到端测试**: 添加自动化测试覆盖消息发送接收流程
4. **监控告警**: 添加消息发送失败的监控和告警
