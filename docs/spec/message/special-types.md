# 特殊消息类型处理

本文档说明非 TEXT 消息的处理规则，包括输入状态、对话提示、系统通知。

## 消息类型概览

- TEXT (1) - 文本消息 - 存储到 message_history
- TYPING_START (2) - 开始输入 - 不存储到 message_history
- TYPING_END (3) - 结束输入 - 不存储到 message_history
- CHAT_INFO (4) - 对话提示信息 - 存储到 message_history
- NOTIFICATION (9) - 系统通知 - 不存储到 message_history

## TYPING 输入状态

### 设计目标

模拟真人输入状态，提升对话真实感。

### 消息结构

**TYPING_START**：

```json
{
  "msg_id": "client_1710001111222_abc123",
  "from_qiao_id": "qiao_user001",
  "to_qiao_id": "qiao_xm001",
  "conv_id": "conv_xyz789",
  "content": "",
  "message_type": 2,
  "supports_typing": true,
  "sent_time": 1710001111222
}
```

**TYPING_END**：

```json
{
  "msg_id": "client_1710001111333_def456",
  "from_qiao_id": "qiao_user001",
  "to_qiao_id": "qiao_xm001",
  "conv_id": "conv_xyz789",
  "content": "",
  "message_type": 3,
  "supports_typing": true,
  "sent_time": 1710001111333
}
```

### 服务端处理

**缓冲策略**：

TYPING 消息影响 buffer 的计时器策略，详见 [buffer.md](buffer.md#状态转换规则)

- TEXT → TYPING_START：取消微计时器，设置宏计时器（32秒）
- TYPING_START → TEXT：取消宏计时器，设置微计时器（3秒）
- TYPING_START → TYPING_END：设置微计时器（3秒）

**存储**：

TYPING 消息仅用于实时输入状态，不写入 message_history。

### 客户端处理

**显示规则**：

- 收到 TYPING_START：显示"对方正在输入..."
- 收到 TYPING_END：隐藏输入状态
- 收到 TEXT：立即隐藏输入状态
- 30秒超时：自动隐藏输入状态
- 用户发送消息：立即隐藏输入状态

**服务端不发送 TYPING_END**：

AI 响应时只发送 TEXT 消息，客户端通过以下方式自动隐藏：

- 收到 TEXT 消息时立即隐藏
- 30秒超时自动隐藏

详见 docs/spec/client/base/contacts-and-chat.md

## CHAT_INFO 对话提示信息

### 设计目标

在聊天界面向用户展示状态信息，不需要 AI 处理。

### 消息类型枚举

- CONTACT_ADDED (1) - 对方已将你添加为联系人
- MESSAGE_BLOCKED (2) - 消息已发出，但对方拒收了
- NOT_FRIEND (3) - 对方还没有添加你为联系人

### 消息结构

**不带 action 的消息**：

```json
{
  "msg_id": "223788765171154945",
  "from_qiao_id": "system",
  "to_qiao_id": "qiao_user_001",
  "message_type": 4,
  "content": "对方已将你添加为联系人",
  "sent_time": 1710001112000
}
```

**带 action 的消息**：

```json
{
  "msg_id": "223788765171154946",
  "from_qiao_id": "system",
  "to_qiao_id": "qiao_user_001",
  "message_type": 4,
  "content": "消息已发出，但对方拒收了",
  "action": {
    "type": "mark_message_failed",
    "target_msg_id": "client_1710001111222_abc123"
  },
  "sent_time": 1710001113000
}
```

### action 字段

**action 类型枚举**：

- MARK_MESSAGE_FAILED - 标记消息为失败

**字段说明**：

- type - 操作类型（mark_message_failed）
- target_msg_id - 目标消息ID（客户端生成的消息ID）

### 架构设计

**三层函数架构**：

```
业务层 (Business Layer)
  ↓ 调用: send_chat_info(to_qiao_id, conv_id, content)
  ↓ 业务层负责: 从 CHAT_INFO_TEMPLATES 获取文本
消息服务层 (Message Service)
  ↓ 调用: send_message(from_qiao_id="system", to_qiao_id, conv_id, content, message_type=CHAT_INFO)
  ↓ 调用: _send_message_internal(...)
Provider层 (LeanCloud)
  ↓ 调用: provider.send_message_as_system(to_qiao_id, conv_id, content)
  ↓ 处理: from="system" 等协议字段
LeanCloud REST API
```

### Content 字段设计

content 字段直接存储最终显示文本。

**使用预定义模板**：

业务层从 CHAT_INFO_TEMPLATES 获取文本，调用 send_chat_info() 传入文本。

**模板定义**：

- CONTACT_ADDED: "对方已将你添加为联系人"
- MESSAGE_BLOCKED: "消息已发出，但对方拒收了"
- NOT_FRIEND: "对方还没有添加你为联系人"

### 发送场景

**1. CONTACT_ADDED - 对方已将你添加为联系人**

当用户成功添加联系人后，系统自动发送此消息。

**2. MESSAGE_BLOCKED - 消息已发出，但对方拒收了**

当用户发送的消息被对方屏蔽时，系统自动发送此消息。

**3. NOT_FRIEND - 对方还没有添加你为联系人**

当用户向未添加自己为联系人的对方发送消息时，系统自动发送此消息。

### 客户端显示规则

**聊天窗口内显示**：

- 居中显示
- 灰色文字
- 小字体
- 不显示头像
- 不显示时间（可选）

**聊天列表显示**：

- 最后一条消息显示对话提示信息内容
- 灰色文字
- 不计入未读数

### 存储规则

存储到 message_history 表：

- from_type: 4 (system)
- from_id: 0
- from_qiao_id: "system"
- message_type: 4 (CHAT_INFO)
- content: 完整文本
- message_metadata: 包含 action（如果有）

## Block 功能和消息拒收

### Block 场景

**场景1：用户 Block AI 实例**

- 用户在联系人详情页点击"屏蔽"按钮
- 更新 contacts.is_blocked = 1
- 用户发送消息时，只存储消息和上下文，不进行 AI 处理
- 发送 CHAT_INFO 消息：`"消息已发出，但对方拒收了"`

**场景2：AI 实例 Block 用户**

- LLM 响应中包含 block_user 动作
- 更新 ai_instances.status = 3 (blocked)
- 用户发送消息时，只存储消息和上下文，不进行 AI 处理
- 发送 CHAT_INFO 消息：`"消息已发出，但对方拒收了"`

**场景3：用户不是 AI 实例的所有者（不是对方好友）**

- 在 contacts 表中检查是否存在有效联系人记录
- 如果没有有效联系人，只存储消息和上下文
- 发送 CHAT_INFO 消息：`"对方还没有添加你为联系人"`

### 处理流程

**逻辑步骤**：

1. 检查联系人关系
   - 如果不存在 → 场景3：发送 NOT_FRIEND 提示
   - 如果 is_blocked → 场景1：发送 MESSAGE_BLOCKED 提示
2. 检查 AI 实例状态
   - 如果 status == 3 (blocked) → 场景2：发送 MESSAGE_BLOCKED 提示
3. 正常处理消息

## NOTIFICATION 系统通知

### 设计目标

推送系统通知到客户端，不存储到 message_history。

### 消息结构

```json
{
  "msg_id": "223788765171154947",
  "from_qiao_id": "system",
  "to_qiao_id": "qiao_user_b",
  "message_type": 9,
  "notification_type": 1,
  "action": {
    "type": "navigate",
    "target": "contact_requests",
    "params": {
      "request_id": "req_123"
    }
  },
  "data": {
    "request_id": "req_123",
    "from_qiao_id": "qiao_user_a",
    "from_nickname": "用户A",
    "from_avatar": "https://cdn.example.com/users/qiao_user_a.webp",
    "message": "你好，我想添加你为联系人"
  },
  "sent_time": 1710001114000
}
```

### 字段说明

- notification_type - 通知类型（1=联系人请求）
- action - 客户端操作对象
- data - 通知数据（用于显示）

### 通知类型枚举

**NotificationType**：

- CONTACT_REQUEST (1) - 联系人请求通知

**NotificationActionType**：

- navigate - 导航到指定页面
- refresh - 刷新数据
- badge - 更新角标数量

**NotificationTarget**：

- contact_requests - 联系人请求页面
- contacts - 联系人列表页面

### action 对象

- type - 操作类型（navigate/refresh/badge）
- target - 操作目标（contact_requests/contacts）
- params - 操作参数（可选）

### 存储说明

- 通知消息**不存入** message_history 表
- 存入 notification_push_history 表
- 用于调试、分析和重试

### 客户端处理流程

1. 收到通知消息（message_type=9）
2. 解析 notification_type 确定通知类别
3. 解析 action 对象确定操作类型
4. 根据 action.type 执行相应操作：
   - navigate: 跳转到 action.target 页面
   - refresh: 刷新 action.target 数据
   - badge: 更新 action.target 角标
5. 使用 data 对象显示通知内容

### 发送场景

**联系人请求通知**：

用户A发送联系人请求给用户B时，系统向用户B推送通知。
