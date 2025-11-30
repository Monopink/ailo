# 通知消息

通知消息负责在联系人请求流程中向用户发送实时通知和对话提示。

## 核心设计原则

### CHAT_INFO vs NOTIFICATION

系统使用两种不同的消息类型处理通知：

**CHAT_INFO (message_type=4)**：

- 用途：聊天界面的信息提示
- 需要 conv_id
- 存储到 message_history 表
- 显示在聊天界面中
- 例如："对方已将你添加为联系人"

**NOTIFICATION (message_type=9)**：

- 用途：系统通知推送
- 不需要 conv_id（设为空字符串）
- 存储到 notification_push_history 表
- 不显示在聊天界面中
- 包含 action 和 data，用于前端导航
- 例如：好友申请通知

### 为什么不提供列表查询接口

好友申请采用消息推送机制，不提供列表查询接口：

**原因**：

- 好友申请是实时性很强的功能，通过消息推送更及时
- 申请有效期短（7 天），不需要长期存储和查询
- 客户端本地存储即可满足需求
- 减少不必要的 API 调用

**数据流**：

1. 发送申请 → 调用 POST /api/v1/contact-requests
2. 接收申请 → 通过 NOTIFICATION 消息推送
3. 客户端存储 → 存储到本地数据库（IndexedDB/SQLite）
4. 查看列表 → 直接读取本地数据库
5. 处理申请 → 调用接受/忽略接口

## CHAT_INFO 消息

### 使用场景

在对话中显示系统提示信息：

- 对方接受了你的好友申请
- 联系人信息变更
- 对话设置变更

### 消息格式

```json
{
  "message_type": 4,
  "conv_id": "conv_xyz789",
  "content": "已添加为联系人",
  "info_type": 1
}
```

**字段说明**：

- message_type - 固定为 4（CHAT_INFO）
- conv_id - 对话 ID（必需）
- content - 提示文本
- info_type - 信息类型枚举（见下文）

### 信息类型

定义在 `backend/app/enums/message.py` - `ChatInfoType`：

- CONTACT_ADDED (1) - 已添加为联系人
- CONTACT_DELETED (2) - 联系人已删除
- CONTACT_BLOCKED (3) - 联系人已屏蔽
- SETTINGS_CHANGED (4) - 设置已变更

### 发送时机

**对方接受好友申请**：

- 触发：用户 B 接受用户 A 的好友申请
- 接收方：用户 A
- 内容：使用 CHAT_INFO_TEMPLATES 中的 CONTACT_ADDED 模板
- conv_id：用户 A 与用户 B 的对话 ID

**实现位置**：

- `backend/app/services/contact/request_service.py` - accept_request 方法
- 调用消息发送服务发送 CHAT_INFO 消息

### 存储

- 表：message_history
- 字段：
  - message_type = 4
  - conv_id = 对话 ID
  - content = 提示文本
  - info_type = 信息类型

详见：[data-dict/message.md](../../data-dict/message.md)

## NOTIFICATION 消息

### 使用场景

系统级通知推送，不属于任何对话：

- 收到好友申请
- 系统公告
- 账号安全提醒

### 消息格式

```json
{
  "message_type": 9,
  "conv_id": "",
  "content": {
    "notification_type": 1,
    "action": {
      "type": "navigate",
      "target": "contact_requests"
    },
    "data": {
      "request_id": "req_123",
      "from_qiao_id": "qiao_user001",
      "from_nickname": "小明",
      "from_avatar": "assets://1234",
      "message": "你好，我想加你为好友"
    }
  }
}
```

**字段说明**：

- message_type - 固定为 9（NOTIFICATION）
- conv_id - 固定为空字符串（不属于任何对话）
- content - 通知内容对象
  - notification_type - 通知类型枚举
  - action - 前端操作指令
  - data - 通知数据

### 通知类型

定义在 `backend/app/enums/message.py` - `NotificationType`：

- CONTACT_REQUEST (1) - 好友申请
- SYSTEM_ANNOUNCEMENT (2) - 系统公告
- ACCOUNT_SECURITY (3) - 账号安全

### Action 指令

指导前端如何处理通知：

**navigate（导航）**：

- type: "navigate"
- target: 目标页面
  - "contact_requests" - 好友申请列表
  - "settings" - 设置页面
  - "profile" - 个人资料

**open_conversation（打开对话）**：

- type: "open_conversation"
- conv_id: 对话 ID

**external_link（外部链接）**：

- type: "external_link"
- url: 链接地址

### 发送时机

**收到好友申请**：

- 触发：用户 A 向用户 B 发送好友申请
- 接收方：用户 B
- notification_type: CONTACT_REQUEST (1)
- action: navigate to contact_requests
- data: 包含申请人信息和申请消息

**实现位置**：

- `backend/app/services/contact/request_service.py` - create_request 方法
- 判断 to_type=USER 时发送 NOTIFICATION

### 存储

- 表：notification_push_history
- 字段：
  - notification_type - 通知类型
  - recipient_qiao_id - 接收人 qiao_id
  - content - 通知内容（JSON）
  - is_read - 是否已读
  - read_at - 阅读时间

详见：[data-dict/notification.md](../../data-dict/notification.md)

## 客户端处理

### 接收 NOTIFICATION

**流程**：

1. **接收消息**：
   - 通过 LeanCloud IM SDK 接收
   - message_type = 9

2. **解析内容**：
   - 提取 notification_type
   - 提取 action 和 data

3. **存储到本地**：
   - 存储到本地数据库（IndexedDB/SQLite）
   - 表结构：contact_requests_local
   - 字段：request_id, from_qiao_id, from_profile, message, received_at

4. **显示通知**：
   - 显示系统通知（操作系统级别）
   - 更新应用内未读数

5. **处理 action**：
   - 用户点击通知时，根据 action 导航到相应页面

### 查看申请列表

**流程**：

1. **读取本地数据库**：
   - 查询 contact_requests_local 表
   - 按 received_at DESC 排序

2. **显示列表**：
   - 显示申请人头像、昵称、申请消息
   - 显示"接受"和"忽略"按钮

3. **处理申请**：
   - 点击"接受" → 调用 POST /api/v1/contact-requests/{id}/accept
   - 点击"忽略" → 调用 POST /api/v1/contact-requests/{id}/ignore
   - 成功后从本地数据库删除该记录

### 接收 CHAT_INFO

**流程**：

1. **接收消息**：
   - 通过 LeanCloud IM SDK 接收
   - message_type = 4
   - 包含 conv_id

2. **存储到本地**：
   - 存储到消息历史表
   - 与普通消息一起显示

3. **显示在对话中**：
   - 显示为系统提示（灰色、居中）
   - 不显示头像和发送者信息

## 消息模板

### CHAT_INFO 模板

定义在 `backend/app/constants/message.py` - `CHAT_INFO_TEMPLATES`：

```python
CHAT_INFO_TEMPLATES = {
    "CONTACT_ADDED": "已添加为联系人",
    "CONTACT_DELETED": "联系人已删除",
    "CONTACT_BLOCKED": "联系人已屏蔽",
}
```

### NOTIFICATION 模板

根据 notification_type 动态生成：

**CONTACT_REQUEST**：

- 标题："新的好友申请"
- 内容："{from_nickname} 请求添加你为好友"
- action: navigate to contact_requests

## 异常处理

### 发送失败

**CHAT_INFO 发送失败**：

- 非关键操作，记录 warning 日志
- 不影响业务流程（请求状态仍然更新）
- 用户可能看不到提示，但不影响功能

**NOTIFICATION 发送失败**：

- 非关键操作，记录 warning 日志
- 不影响业务流程（请求记录已创建）
- 用户可能收不到通知，但可以通过其他方式查看

### 消息重复

**客户端去重**：

- 使用 request_id 作为唯一标识
- 收到重复消息时，检查本地数据库
- 如果已存在，忽略该消息

### 消息过期

**客户端清理**：

- 定期清理过期的申请记录（7 天前）
- 避免本地数据库膨胀

## 监控建议

### 关键指标

- NOTIFICATION 发送成功率
- CHAT_INFO 发送成功率
- 平均通知到达时间
- 客户端本地存储大小

### 告警规则

- NOTIFICATION 发送失败率 > 5%
- CHAT_INFO 发送失败率 > 5%
- 通知到达时间 > 5 秒（可能是 LeanCloud 问题）

## 相关文档

- [request-flow.md](request-flow.md) - 联系人请求流程
- [spec/message/special-types.md](../message/special-types.md) - 特殊消息类型详解
- [api/leancloud-message.md](../../api/leancloud-message.md) - 消息服务 API
- [data-dict/message.md](../../data-dict/message.md) - 消息数据表
- [data-dict/notification.md](../../data-dict/notification.md) - 通知数据表
