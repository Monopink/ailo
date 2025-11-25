# 消息流程设计

## 消息结构设计

### MVP阶段消息结构（LeanCloud传输格式）

```json
{
  "msg_id": "client_1710001111222_abc123",  // 消息ID（客户端生成或服务端生成）
  "from": "qiao_user001",                   // 发送者qiao_id
  "to": "qiao_xm001",                       // 接收者qiao_id
  "conv_id": "conv_xyz789",                 // 对话ID（后端管理）
  "content": "你好",                         // 消息内容
  "message_type": 1,                        // 消息类型：1=TEXT, 2=TYPING_START, 3=TYPING_END, 4=CHAT_INFO, 9=NOTIFICATION
  "supports_typing": true,                  // 客户端是否支持输入状态
  "sent_time": 1710001111222                // 发送时间戳（毫秒）
}
```

### 消息ID设计

**单一ID字段设计：**

消息使用单一的`msg_id`字段，通过消息方向判断ID类型：

1. **用户发送的消息**
   - `msg_id`由客户端生成
   - 格式：`client_{timestamp}_{random}`
   - 示例：`client_1710001111222_abc123`
   - 用途：客户端消息去重、状态追踪、失败重试

2. **AI/系统发送的消息**
   - `msg_id`由服务端生成（Snowflake ID）
   - 格式：数字ID
   - 示例：`223788765171154945`
   - 用途：服务端消息管理和查询

3. **转发消息**
   - 保持原始`msg_id`不变
   - 用户A → 服务端 → 用户B，`msg_id`始终是用户A生成的客户端ID
   - 服务端只生成`msg_id_server`用于数据库存储

**数据库存储：**

message_history表存储两个ID：

- `msg_id_server`：服务端统一生成的Snowflake ID（主键）
- `msg_id_client`：客户端生成的ID（仅用户消息有值）

**消息ID使用场景：**

- **客户端发送消息**：生成`msg_id`（客户端ID），发送到LeanCloud
- **服务端接收消息**：生成`msg_id_server`，存储到数据库，保持`msg_id`不变
- **服务端发送消息**：生成`msg_id`（服务端ID），发送到LeanCloud
- **消息发送失败**：通过`msg_id`标识失败的消息
- **消息重试**：使用`msg_id`避免重复发送

### supports_typing字段说明

- `true`: 客户端支持输入状态（小程序）
  - 会发送TYPING_START和TYPING_END消息
  - 服务端使用智能缓冲策略
- `false`或不存在: 客户端不支持输入状态（公众号等）
  - 不会发送输入状态消息
  - 服务端使用NO_TYPING_WAIT策略

## 消息处理流程

客户端与服务端之间通信使用统一的Leancloud系统对话。

```mermaid
flowchart TB
    n1["客户端发送消息"] --> n2["Leancloud"]
    n2 --> n3["Webhook接收 (webhook.py)"]
    n3 --> n4["消息验证和格式转换"]
    n4 --> n5["消息服务核心 (core.py)"]
    n5 --> n6["安全检测 (security.py)"]
    n6 --> n7["频率限制 (rate_limiter.py)"]
    n7 --> n8["消息缓冲 (buffer.py)"]
    n8 --> n9["AI服务 (ai/core.py)"]
    n9 --> n10["角色识别 (instance.py)"]
    n10 --> n11["上下文构建 (context.py)"]
    n11 --> n12["提示词生成 (prompt.py)"]
    n12 --> n13["LLM调用 (llm_client.py)"]
    n13 --> n14["响应处理"]
    n14 --> n15["消息发送 (sender.py)"]
    n15 --> n16["LeanCloud发送"]
    n16 --> n17["用户接收"]

    n5 --> n18["存入message_history"]
    n15 --> n19["发送成功"] & n20["发送失败"]
    n20 --> n21["记录message_delivery_failures"]
```

## 详细流程设计

### 1. 消息接收阶段 (services/message/providers/leancloud/webhook.py)

处理步骤：

- 验证Webhook签名
- 解析LeanCloud消息格式
- 转换为内部消息格式
- 调用消息服务核心处理

### 2. 消息处理阶段 (services/message/core.py)

处理步骤：

- 安全检测: 检查消息内容是否违规
- 频率限制: 防止用户刷屏，限制发送频率
- 消息缓冲: 短时间内多条消息合并处理
- 消息加密: 敏感内容加密存储

### 3. 消息缓冲机制 (services/message/buffer.py)

#### 设计理念

类似于人会等待对方说完整件事然后再回复，系统通过智能缓冲策略合并短时间内的多条消息。

#### 缓冲配置（存储在system_configs表）

```python
# 配置项
MESSAGE_BUFFER_NORMAL_WAIT = 3000      # 普通等待：3秒
MESSAGE_BUFFER_TYPING_WAIT = 10000     # 长等待（输入中）：10秒
MESSAGE_BUFFER_TYPING_END_WAIT = 1000  # 短等待（输入结束）：1秒
MESSAGE_BUFFER_NO_TYPING_WAIT = 2000   # 无输入状态等待：2秒
```

#### 缓冲策略逻辑

**1. 客户端不支持输入状态（supports_typing=false或不存在）**

- 使用NO_TYPING_WAIT（2秒）
- 适用于公众号等无法检测输入状态的客户端

**2. 客户端支持输入状态（supports_typing=true）**

根据消息类型使用不同等待时间：

- **TEXT消息**: NORMAL_WAIT（3秒）
  - 用户发送文本消息后等待3秒
  - 如果3秒内有新消息，重置定时器
  - 3秒后开始处理所有缓冲的消息

- **TYPING_START消息**: TYPING_WAIT（10秒）
  - 用户开始输入，进入长等待
  - 给用户充足时间完成输入
  - 10秒内如果收到新消息，重置定时器

- **TYPING_END消息**: TYPING_END_WAIT（1秒）
  - 用户结束输入，进入短等待
  - 快速响应用户
  - 1秒后开始处理

#### 核心设计决策

**1. 使用 ai_message_buffer 表管理缓冲状态**

- 消息到达后仅更新/创建 `ai_message_buffer` 窗口，表中保存 WAITING_WAKEUP → OPEN → LOCKED → COMPLETE 状态机及 `micro/macro_expires_at_ms`、`last_message_category` 等元数据。
- Buffer 不存储消息内容，只负责聚合窗口与抢占逻辑，确保新窗口可以覆盖旧请求。

**2. 消息内容写入 ai_conversation_items（纯内容）**

- 每条用户/AI 消息立即写入 `ai_conversation_items`，只有 `{role, message_type, text_content, media_url, media_metadata, is_excluded_from_context}` 等简单字段。
- 攻击或需要排除的消息只需将 `is_excluded_from_context` 标记为 1，内容仍完整保存，后续上下文会自动跳过。

**3. LLM 合并与时间标记由 converter 层负责**

- 查询上下文时把 `ai_conversation_items` 转为业务格式，再由 converter 合并连续同 role 的条目。
- `_format_time_prefix` 在构造 LLM 消息时才生成人性化前缀（例如 `[11-18(五天前) 17:19]` / `今天17:19`），数据库中仅保留原始文本，彻底解耦存储与展示。

**4. 服务重启处理**

- buffer 状态和消息内容都在数据库里，服务重启不会丢失。
- 定时器依赖数据库时间戳，下一次扫描或新消息即可恢复聚合流程。

**5. 函数式编程**

- 使用纯函数，不使用类。
- 状态存储在数据库，不在内存，保持 MVP 的函数式风格。

### 4. 输入状态处理机制

**说明：** 输入状态的客户端实现逻辑请参考 `docs/prototype/minipg.md` 文档。

**服务端处理：**

服务端不发送TYPING_END消息，客户端通过以下方式自动隐藏输入状态：

- 收到TEXT消息时立即隐藏
- 30秒超时自动隐藏
- 用户发送消息时立即隐藏

### 5. 对话提示信息处理机制（message_type=4）

#### 5.1 对话提示信息类型

对话提示信息用于在聊天界面向用户展示状态信息，不需要AI处理。

**消息类型：**

```python
class ChatInfoType(IntEnum):
    CONTACT_ADDED = 1        # 对方已将你添加为联系人
    MESSAGE_BLOCKED = 2      # 消息已发出，但对方拒收了
    NOT_FRIEND = 3           # 对方还没有添加你为联系人
```

#### 5.2 消息结构

**不带 action 的消息**：

```json
{
  "msg_id": "223788765171154945",
  "from": "system",
  "to": "qiao_user_001",
  "message_type": 4,
  "content": "对方已将你添加为联系人",
  "sent_time": 1710001112000
}
```

**带 action 的消息**：

```json
{
  "msg_id": "223788765171154946",
  "from": "system",
  "to": "qiao_user_001",
  "message_type": 4,
  "content": "消息已发出，但对方拒收了",
  "action": {
    "type": "mark_message_failed",
    "target_msg_id": "client_1710001111222_abc123"
  },
  "sent_time": 1710001113000
}
```

**action 字段说明**：

- `type`: 操作类型（mark_message_failed）
- `target_msg_id`: 目标消息ID（客户端生成的消息ID）

**action 类型枚举**：

```python
class ChatInfoActionType(str, Enum):
    MARK_MESSAGE_FAILED = "mark_message_failed"  # 标记消息为失败
```

#### 5.3 架构设计

**架构分层：**

对话提示信息的发送采用三层函数架构：

```
业务层 (Business Layer)
  ↓ 调用: send_chat_info(to_qiao_id, conv_id, content)
  ↓ 业务层负责: 从CHAT_INFO_TEMPLATES获取文本
消息服务层 (Message Service)
  ↓ 调用: send_message(from_qiao_id="system", to_qiao_id, conv_id, content, message_type=CHAT_INFO)
  ↓ 调用: _send_message_internal(...)
Provider层 (LeanCloud)
  ↓ 调用: provider.send_message_as_system(to_qiao_id, conv_id, content)
  ↓ 处理: from="system"等协议字段
LeanCloud REST API
```

**Content字段设计：**

对话提示信息的content字段直接存储最终显示文本：

1. **使用预定义模板：**
   - 业务层从CHAT_INFO_TEMPLATES获取文本
   - 调用send_chat_info()传入文本
   - 文本存入content字段
   - 客户端直接显示content字段

示例代码：

```python
from enums.templates import CHAT_INFO_TEMPLATES, ChatInfoType

content = CHAT_INFO_TEMPLATES[ChatInfoType.CONTACT_ADDED]
await send_chat_info(
    db=db,
    to_qiao_id=user_qiao_id,
    conv_id=conv_id,
    content=content,
)
```

#### 5.4 发送场景

1. CONTACT_ADDED - 对方已将你添加为联系人

当用户成功添加联系人后，系统自动发送此消息。

2. MESSAGE_BLOCKED - 消息已发出，但对方拒收了

当用户发送的消息被对方屏蔽时，系统自动发送此消息。

3. NOT_FRIEND - 对方还没有添加你为联系人

当用户向未添加自己为联系人的对方发送消息时，系统自动发送此消息。

#### 5.5 显示规则

客户端处理：

1. 聊天窗口内显示
   - 居中显示
   - 灰色文字
   - 小字体
   - 不显示头像
   - 不显示时间（可选）

2. 聊天列表显示
   - 最后一条消息显示对话提示信息内容
   - 灰色文字
   - 不计入未读数

#### 5.6 存储规则

- 存储到message_history表
- from_type = 4 (system)
- from_id = 0
- from_qiao_id = "system"
- message_type = 4 (CHAT_INFO)
- content字段包含完整文本

### 6. Block功能和消息拒收处理

#### 6.1 Block场景

**场景1：用户Block AI实例**

- 用户在联系人详情页点击"屏蔽"按钮
- 更新contacts.is_blocked = 1
- 用户发送消息时，只存储消息和上下文，不进行AI处理
- 发送CHAT_INFO消息：`"消息已发出，但对方拒收了"`

**场景2：AI实例Block用户**

- LLM响应中包含block_user动作
- 更新ai_instances.status = 3 (blocked)
- 用户发送消息时，只存储消息和上下文，不进行AI处理
- 发送CHAT_INFO消息：`"消息已发出，但对方拒收了"`

**场景3：用户不是AI实例的所有者（不是对方好友）**

- 在 contacts 表中检查是否存在 `user_qiao_id = 当前用户`、`contact_qiao_id = AI qiao_id` 且 `contact_type = 2`、`is_deleted = 0` 的记录
- 如果没有有效联系人，只存储消息和上下文
- 发送CHAT_INFO消息：`"对方还没有添加你为联系人"`

### 7. 消息发送失败处理

**说明：** 消息发送失败的客户端实现逻辑请参考 `docs/prototype/minipg.md` 文档。

#### 7.1 失败场景

**LeanCloud层面发送失败：**

- 网络错误
- LeanCloud服务异常
- 消息格式错误

**业务层面发送失败（拒收）：**

- 用户被屏蔽
- AI实例屏蔽用户
- 用户不是对方好友

#### 7.2 服务端拒收标记

服务端通过发送CHAT_INFO消息通知客户端消息被拒收，客户端标记消息为失败状态。

### 8. 通知消息处理机制（message_type=9）

#### 8.1 消息结构

```json
{
  "msg_id": "223788765171154947",
  "from": "system",
  "to": "qiao_user_b",
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
    "from_avatar": "avatar_url",
    "message": "你好，我想添加你为联系人"
  },
  "sent_time": 1710001114000
}
```

#### 8.2 字段说明

- `notification_type`: 通知类型（1=联系人请求）
- `action`: 客户端操作对象
  - `type`: 操作类型（navigate/refresh/badge）
  - `target`: 操作目标（contact_requests/contacts）
  - `params`: 操作参数
- `data`: 通知数据（用于显示）

#### 8.3 通知类型

**NotificationType**:

- CONTACT_REQUEST (1): 联系人请求通知

**NotificationActionType**:

- navigate: 导航到指定页面
- refresh: 刷新数据
- badge: 更新角标数量

**NotificationTarget**:

- contact_requests: 联系人请求页面
- contacts: 联系人列表页面

#### 8.4 存储说明

- 通知消息**不存入** message_history 表
- 存入 notification_push_history 表
- 用于调试、分析和重试

#### 8.5 客户端处理流程

1. 收到通知消息（message_type=9）
2. 解析 notification_type 确定通知类别
3. 解析 action 对象确定操作类型
4. 根据 action.type 执行相应操作：
   - navigate: 跳转到 action.target 页面
   - refresh: 刷新 action.target 数据
   - badge: 更新 action.target 角标
5. 使用 data 对象显示通知内容

### 9. AI处理阶段 (services/ai/core.py)

处理步骤：

- 实例识别: 根据conversation_id识别AI实例
- 上下文管理: 获取历史对话，构建上下文
- 提示词构建: 根据角色特征生成系统提示词
- LLM调用: 调用大模型生成回复
- 响应处理: 格式化回复内容

### 10. 错误处理和重试机制

消息处理失败：

- 验证失败: 记录日志，返回400错误
- 频率超限: 返回429错误，提示用户稍后再试
- 内容违规: 记录违规日志，发送警告消息

AI服务异常：

- LLM调用失败: 使用预设回复或重试
- 上下文异常: 重建上下文或使用简化版本
- 超时处理: 设置合理超时时间，超时返回默认回复

发送失败处理：

- 网络异常: 记录到message_delivery_failures表
- 重试机制: 指数退避重试，最多重试3次
- 最终失败: 记录日志，通知管理员

## 消息事件 Schema

本节定义消息系统在"Webhook → 管线 → 缓冲/AI → 发送"各阶段共享的事件结构。

### 版本与命名

- `schema_version`：当前文档版本 `1.0.0`，语义化版本号
- `event_type`：小写蛇形命名，区分 `inbound_message`、`outbound_message` 等
- 所有时间均为 Unix 毫秒时间戳
- 所有身份字段使用 `qiao_id`（对外 ID）

### 公共字段

| 字段名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `schema_version` | string | ✅ | 文档版本 `1.0.0` |
| `event_type` | string | ✅ | 事件类型：`inbound_message` / `outbound_message` |
| `message_type` | int | ✅ | 消息类别：`1=TEXT`, `2=TYPING_START`, `3=TYPING_END`, `4=CHAT_INFO`, `9=NOTIFICATION` |
| `conversation_id` | string | ✅ | 系统内部 conv_id |
| `from_qiao_id` | string | ✅ | 发送方 qiao_id |
| `to_qiao_id` | string | ✅ | 接收方 qiao_id |
| `content` | string | ✅ | 文本内容；typing 类事件可为空字符串 |
| `sent_at_ms` | int | ✅ | 发送时间（毫秒） |
| `msg_id_server` | string | ✅ | 服务端 Snowflake ID |
| `msg_id_client` | string/null | 条件 | 客户端生成的 ID，仅用户消息必填 |
| `msg_id_provider_inbound` | string/null | 条件 | 第三方入站 ID（LeanCloud `msgId`） |
| `msg_id_provider_outbound` | string/null | 条件 | 第三方出站 ID（发送成功后回填） |
| `supports_typing` | bool | ✅ | 客户端是否支持 typing |
| `client_sent_time` | int/null | 条件 | 客户端发送时间 |
| `metadata` | object | ✅ | 业务扩展字段 |
| `provider_metadata` | object | ✅ | 第三方原始字段 |

**metadata 白名单**：

- `action`：系统消息附带的 action 描述
- `notification_type`：通知类型枚举
- `rate_limit_bucket`：速率限制统计窗口
- `encryption` / `encryption_version`：传输加密算法与版本

### InboundMessageEvent 示例

```jsonc
{
  "schema_version": "1.0.0",
  "event_type": "inbound_message",
  "message_type": 1,
  "conversation_id": "conv_xyz789",
  "from_qiao_id": "qiao_user001",
  "to_qiao_id": "qiao_xm001",
  "content": "你好",
  "sent_at_ms": 1710001111222,
  "msg_id_server": "msg_223788765171154945",
  "msg_id_client": "client_1710001111222_abc123",
  "msg_id_provider_inbound": "nYH9iBSBS_uogCEgvZwE7Q",
  "msg_id_provider_outbound": null,
  "supports_typing": true,
  "client_sent_time": 1710001111222,
  "metadata": {
    "encryption": "base64",
    "encryption_version": "v1"
  },
  "provider_metadata": {
    "lc_from": "qiao_user001",
    "lc_conv_id": "68edda0a554ecc6e8843b246"
  }
}
```

### OutboundMessageEvent 示例

```jsonc
{
  "schema_version": "1.0.0",
  "event_type": "outbound_message",
  "message_type": 1,
  "conversation_id": "conv_xyz789",
  "from_qiao_id": "qiao_xm001",
  "to_qiao_id": "qiao_user001",
  "content": "我在呢，刚才看到你发的消息啦～",
  "sent_at_ms": 1710002222333,
  "msg_id_server": "msg_223788765171155999",
  "msg_id_client": null,
  "msg_id_provider_inbound": null,
  "msg_id_provider_outbound": null,
  "supports_typing": true,
  "client_sent_time": null,
  "metadata": {
    "encryption": "base64",
    "encryption_version": "v1"
  },
  "provider_metadata": {
    "lc_conv_id": "68edda0a554ecc6e8843b246"
  }
}
```

## 消息加密机制

### 背景

客户端与服务端支持统一的"消息加密"机制，短期内以 **Base64 编码** 作为占位，实现接口与 metadata 约束；后期再切换到 **AES-256-GCM** 或其他算法。

### 架构

```
客户端 → LeanCloud → Webhook
    ↑                 ↓
  Base64 encode   decrypt_from_transport()
```

**Outbound（服务端→客户端）**：
- `services/message/sender.py` 在 `_send_message_internal` 中调用 `encrypt_for_transport()`
- 返回的 `encrypted_content` 写入 LeanCloud payload
- `metadata.encryption/encryption_version` 合并到消息 JSON

**Inbound（客户端→服务端）**：
- Webhook 解析 `inner_message` 时读取 `encryption/enc_version`
- 调用 `decrypt_from_transport()`，得到明文后再进入 buffer/AI
- 若客户端发送明文，则缺少 `encryption` 字段，服务端直接透传

**持久化**：
- `metadata` 新增 `encryption / encryption_version` 字段
- 映射到 `message_history.message_metadata`

### 模块说明

文件：`backend/app/services/message/encryption.py`

| 函数 | 作用 |
|------|------|
| `encrypt()` / `decrypt()` | 算法无关的基础接口，支持 `BASE64`、`AES_256_GCM` |
| `_encode_base64` / `_decode_base64` | MVP 占位实现，**不需要 key** |
| `_encrypt_aes_256_gcm` / `_decrypt_aes_256_gcm` | 预留真实加密方案（key 必须 32 bytes） |
| `encrypt_for_transport()` | 使用默认算法（当前 Base64）封装传输逻辑 |
| `decrypt_from_transport()` | 根据 metadata 自动解密；metadata 缺失时返回原文 |

### 配置与后续计划

- 目前 `DEFAULT_ENCRYPTION = base64`，`DEFAULT_VERSION = v1`，不依赖任何 key
- 未来切换 AES：
  - 在配置中心（如 system_configs）保存 key/版本
  - 在 `encrypt_for_transport()` / `decrypt_from_transport()` 中读取 key
  - metadata 中新增 `key_id`、`iv` 等字段

### 注意事项

- `cryptography` 已加入 `backend/app/requirements.txt`（版本 `46.0.3`）
- 解密失败会记录 `leancloud_decrypt_failed` 日志，并回退到原文，避免消息丢失
- 任何新增算法必须在 `EncryptionType`、`EncryptionVersion` 枚举与 schema 文档中登记
