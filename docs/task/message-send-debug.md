## 消息收发与打字体验（后端方案） — 2025-11-19

本文件聚焦后端需要落实的修复与演进内容；前端协作指引请见 `docs/task/message-send-debug-frontend.md`。

### 现状快照
- AI 侧已正确产出 `outgoing_messages`，并在 `send_ai_messages_with_typing` → `send_message` 流程中调用 LeanCloud provider。
- Provider 层仍发送“扁平 JSON”，缺少 `_lctype/_lcattrs`，LeanCloud SDK 因此不会把消息解析成 `BusinessMessage`。
- `msg_id_server` 在业务层生成后被丢弃（provider 重新生成），导致消息内容与通道字段不一致。
- `follow_up_hint` 在 schema/解析中存在，但没有消费者。
- Typing 兜底配置固定为 35 WPM，造成长时间等待。
- Provider 组装逻辑散落在 `service.py`、未启用的 `adapter.py`、webhook 中，存在重复实现。

### 后端修复范围

#### 1. 重写 `services/message/providers/leancloud/adapter.py` 的 outbound 功能
- Adapter 负责 **唯一** 的 LeanCloud 编解码实现：构造 TypedMessage payload、解析 webhook 中的 TypedMessage。当前代码库中 outbound builder 从未被任何发送路径调用，inbound 的 `parse_webhook_to_dict` 也还没有接入 webhook 入口，因此本轮必须同时让 `service.send_message*` 和 webhook handler 均改为调用 adapter，避免继续出现两套实现。
- **TypedMessage 格式规范**（通过 REST API 发送时）：
```json
{
  "_lctype": 1,
  "_lcattrs": {
    "msg_id": "msg_xxx",
    "from_qiao_id": "qiao_xxx",
    "to_qiao_id": "qiao_xxx",
    "conv_id": "conv_xxx",
    "content": "encrypted_content",
    "message_type": 1,
    "supports_typing": true,
    "sent_time": 1234567890,
      "encryption": "base64",
      "enc_version": "v1",
      "action": {...},
      "notification_type": 1,
      "data": {...}
    }
  }
  ```
- 构造规则（`build_outbound_typed_message` 函数）：
  - 重命名 `build_outbound_payload` → `build_outbound_typed_message`。
  - `_lctype=1`（与前端 `BusinessMessage` 保持一致）。
  - `_lcattrs` 中包含：`msg_id`（**必填参数**，使用业务层传入的 `msg_id_server`）、`from_qiao_id`、`to_qiao_id`、`conv_id`、`content`、`message_type`、`supports_typing`、`sent_time`、`action`、`notification_type`、`data`、`encryption`、`enc_version` 及其他扩展字段。
  - `extra_fields` 由业务层传入，统一 merge 到 `_lcattrs`，禁止再出现多处手工 JSON 拼接。
- 解析规则（`parse_webhook_to_dict` 函数，已实现）：
  - 读取 `_lctype/_lcattrs`，恢复成中立的业务结构（内容、加密信息、动作、LeanCloud 原始 metadata 等）。
  - 强校验系统会话 ID，与 `system_configs.leancloud_im_service_conversation_id` 对齐。
  - 任何缺失字段直接记录错误并丢弃，避免 silent fail。

#### 2. Provider API 与消息 ID 传递
- **更新顺序**：先更新 `MessageProvider` 协议（base.py），再更新 `LeanCloudProvider` 实现，最后更新调用点。
- `MessageProvider.send_message` 签名中增加 `msg_id: str`（**必填参数**），要求调用方显式传入。
- `LeanCloudProvider.send_message` / `service.send_message` 同步更新签名，调用 `adapter.build_outbound_typed_message` 并传入 `msg_id`。
- `send_message_as_system` 同样遵循 TypedMessage builder，传入 `supports_typing=False`，但依然通过 adapter 保证结构一致。
- `services/message/outbound/sender.py` 中：
  - `send_message` 函数在 L109 生成 `msg_id_server`。
  - `_send_message_internal` 在 L113 调用 provider 时传入 `msg_id=msg_id_server`，确保 `_lcattrs.msg_id` = `message_history.msg_id_server`。
- Provider 层仍会记录 LeanCloud 返回的 `msgId`（`MessageResult.msg_id_provider`），两者分别存入 `msg_id_server` / `msg_id_provider_outbound`。

#### 3. Schema 与冗余代码清理
- 在 `docs/development/message-events-schema.md`、`services/message/schemas.py`、webhook/adapter 等所有引用中 **移除 `follow_up_hint`**，因为没有消费者且会额外透出无意义字段。
- 删除旧的、未被引用的 LeanCloud payload 构造函数；所有发送入口必须调用 adapter。
- 检查是否还存在第二套解析逻辑（如 webhook 中直接 `json.loads(data_str)` 并读取扁平字段），统一改为 `adapter.parse_webhook_to_dict`。

#### 4. 传输内容策略与未来加密
- 由于小程序端受限，短期内直接传递明文内容：`encrypt_for_transport` 返回原文，adapter `_lcattrs` 中不再携带 `encryption` / `enc_version` 字段。
- 保留加密接口设计（函数、参数、类型），便于未来 App 端启用 AES 时最小化改动。
- 一旦切换到支持度更高的终端，再补充编码/解码流程与验收说明。

#### 5. Typing 体验
- 将 `DEFAULT_TYPING_SPEED_WPM` 提升到 **50 WPM**，并重新计算 `DEFAULT_TYPING_SPEED_SECONDS_PER_WORD`。
- 其余角色/模板配置继续由业务管理者调整；若角色没配置，就使用新的 50 WPM 兜底。

### 实施步骤概览
1. **Adapter 重构**（P0 优先级）
   - 重命名 `build_outbound_payload` → `build_outbound_typed_message`。
   - 修改函数签名：`msg_id` 改为必填参数，新增 `supports_typing: bool = True` 参数。
   - 修改返回格式：包装为 `{"_lctype": 1, "_lcattrs": {...}}`。
   - `service.send_message`、`service.send_message_as_system` 调用新的 adapter 函数。
2. **Provider 接口更新**（P0 优先级）
   - 更新 `MessageProvider` 协议（base.py）：`send_message` 添加 `msg_id: str` 必填参数。
   - 更新 `LeanCloudProvider` 实现（__init__.py）：同步签名。
   - 更新 `service.send_message` 和 `service.send_message_as_system`：同步签名。
   - 更新 `_send_message_internal`（outbound/sender.py L113）：传入 `msg_id=msg_id_server`。
3. **Schema/字段清理**（P1 优先级）
   - 移除 `follow_up_hint` 字段：`schemas.py`、`adapter.py`、`webhook.py`、`parser.py`。
   - 删除 `service.py` 中旧的扁平 JSON 构造逻辑（L420-456）。
4. **Typing 常量**（P2 优先级）
   - 修改 `services/ai/queries/transactions.py` L29：`DEFAULT_TYPING_SPEED_WPM = 50`。
   - 重新计算 L30：`DEFAULT_TYPING_SPEED_SECONDS_PER_WORD = 60.0 / 50`。
5. **验证与回归**
   - 端到端：小程序发消息 → 后端 buffer → AI 回复 → LeanCloud → 小程序展示。
   - 数据库：`message_history.msg_id_server` == `_lcattrs.msg_id`，`msg_id_provider_outbound` 保存 LeanCloud `msgId`。
   - 日志：检查 `leancloud_message_sent` 事件中消息体包含 `_lctype=1` 和 `_lcattrs`。

### 验证清单
| 检查项 | 目标 |
| --- | --- |
| LeanCloud payload | 后端日志中 `leancloud_message_sent` 事件的 message 字段包含 `_lctype=1`、`_lcattrs` 字典 |
| msg_id 一致性 | `_lcattrs.msg_id` 等于 `message_history.msg_id_server`（Snowflake ID） |
| Provider 签名 | IDE/类型检查通过，所有实现类、调用点均已更新为 `msg_id: str` 必填参数 |
| follow_up_hint | 项目内无引用（grep 搜索结果为空） |
| Typing 兜底 | 日志中 `typing_speed_seconds_per_word` 约等于 `1.2`（60/50） |
| 内容策略 | 发送日志中 `content` 为明文（无 `_lcattrs.encryption` 字段） |
| 前端接收 | 小程序收到消息后能展示明文，无 "Received non-business message" 警告 |

### 参考
- LeanCloud TypedMessage 规范：`references/leancloud-docs/im/guide/rest.md`
- 前端业务消息类：`frontend/wx-minipg/utils/message/leancloud.js`（BUSINESS_MESSAGE_TYPE=1）
- 前端实现要求：`docs/task/message-send-debug-frontend.md`
