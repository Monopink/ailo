# 特殊消息类型处理

本文档说明非 TEXT 消息的处理规则，包括输入状态、对话提示、系统通知。

## 消息类型与存储规则概览

消息类型枚举值见 [schema.md](schema.md#公共字段)。

- TEXT - 文本消息 - 存储到 `message_history`
- TYPING_START - 开始输入 - 不存储到 `message_history`
- TYPING_END - 结束输入 - 不存储到 `message_history`
- CHAT_INFO - 对话提示信息 - 存储到 `message_history`
- NOTIFICATION - 系统通知 - 不存储到 `message_history`

## TYPING 输入状态

统一约定：`typing` 的客户端发送规则（含 1 秒 buffer）与展示规则以 [typing.md](typing.md) 为准。

### 设计目标

模拟真人输入状态，提升对话真实感。

### 消息结构

字段约束（相对 TEXT）：

- `message_type`：`TYPING_START` 或 `TYPING_END`
- `content`：空字符串

### 服务端处理

缓冲策略：

- TEXT -> TYPING_START：取消微计时器，设置宏计时器（32 秒）
- TYPING_START -> TEXT：取消宏计时器，设置微计时器（3 秒）
- TYPING_START -> TYPING_END：设置微计时器（3 秒）

存储：

- TYPING 消息仅用于实时输入状态，不写入 `message_history`

客户端处理：

- 客户端发送与展示规则（含 `typing_start` 1 秒 buffer）统一遵循 [typing.md](typing.md)

## CHAT_INFO 对话提示信息

### 设计目标

在聊天界面向用户展示状态信息，不需要 AI 处理。

### 消息类型枚举

- CONTACT_ADDED (1) - 对方已将你添加为联系人
- MESSAGE_BLOCKED (2) - 消息已发出，但对方拒收了
- NOT_FRIEND (3) - 对方还没有添加你为联系人

### 消息结构

不带 action 的消息：

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

带 action 的消息：

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

- `type` - 操作类型（`mark_message_failed`）
- `target_msg_id` - 目标消息 ID（客户端生成的消息 ID）
- `reason` - 可选，机器可读原因码（客户端分支不得依赖 content 文案）
- `retry_after_seconds` - 可选，频控场景的重试等待秒数
- `max_message_length_chars` - 可选，超长场景的服务端最大字符数

### 发送场景

1. CONTACT_ADDED：用户成功添加联系人后自动发送
2. MESSAGE_BLOCKED：用户消息被拒收后自动发送
3. NOT_FRIEND：用户向非好友发送消息后自动发送

### 业务失败统一反馈（标记失败 + CHAT_INFO）

当服务端接收入站用户消息后，命中业务拒绝（如拒收、超长、频控）时，必须通过时间线发送 `CHAT_INFO` 并携带 `action=mark_message_failed`，用于客户端将对应 `msg_id_client` 的消息标记为失败。

约束：

- `action.target_msg_id` 必须等于该条用户消息的 `msg_id_client`
- 客户端不得依赖 `content` 文案分支，必须依赖 `action.reason` 等机器字段
- `CHAT_INFO` 作为时间线消息存储到 `message_history` 并通过 fanout 多端同步

### 客户端显示规则

聊天窗口内显示：

- 居中显示
- 灰色文字
- 小字体
- 不显示头像

聊天列表显示：

- 最后一条消息显示对话提示信息内容
- 灰色文字
- 不计入未读数

### 存储规则

存储到 `message_history`：

- `from_type`: 4 (system)
- `from_id`: 0
- `from_qiao_id`: "system"
- `message_type`: 4 (CHAT_INFO)
- `content`: 完整文本
- `message_metadata`: 包含 action（如果有）

## Block 功能和消息拒收

### Block 场景

场景 1：用户 Block AI 实例

- 用户在联系人详情页点击屏蔽按钮
- 更新 `contacts.is_blocked = 1`
- 用户发送消息时，入站用户消息写入 `message_history`；不进入 AI 上下文与 LLM 链路
- 发送 CHAT_INFO 消息并携带 `action=mark_message_failed`

场景 2：AI 实例 Block 用户

- LLM 响应中包含 `block_user` 动作
- 更新 `ai_instances.status = 3` (blocked)
- 用户发送消息时，入站用户消息写入 `message_history`；不进入 AI 上下文与 LLM 链路
- 发送 CHAT_INFO 消息并携带 `action=mark_message_failed`

场景 3：用户不是 AI 实例的所有者（不是对方好友）

- 在 `contacts` 表中检查是否存在有效联系人记录
- 若无有效联系人，入站用户消息写入 `message_history`；不进入 AI 上下文与 LLM 链路
- 发送 CHAT_INFO 消息并携带 `action=mark_message_failed`

### 处理流程

1. 检查联系人关系
2. 检查 AI 实例状态
3. 命中拒收场景时，发送 CHAT_INFO（含 `mark_message_failed`）并结束
4. 未命中拒收场景时，正常进入 buffer/AI 管线

## NOTIFICATION 系统通知

### 设计目标

推送系统通知到客户端，不存储到 `message_history`。

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
      "request_id": "223788765171154968"
    }
  },
  "data": {
    "request_id": "223788765171154968",
    "from_qiao_id": "qiao_user_a",
    "from_nickname": "用户A",
    "from_avatar": "https://cdn.example.com/users/qiao_user_a.webp",
    "message": "你好，我想添加你为联系人"
  },
  "sent_time": 1710001114000
}
```

### 字段说明

- `notification_type` - 通知类型（1=联系人请求）
- `action` - 客户端操作对象
- `data` - 通知数据（用于显示）

### 通知类型枚举

- CONTACT_REQUEST (1) - 联系人请求通知
- `action.type`: `navigate` / `refresh` / `badge`
- `action.target`: `contact_requests` / `contacts`

### 存储说明

- 通知消息不存入 `message_history`
- 存入 `notification_push_history`

### 客户端处理流程

1. 收到通知消息（`message_type=9`）
2. 解析 `notification_type`
3. 解析 `action`
4. 根据 `action.type` 执行对应动作
5. 使用 `data` 显示通知内容
