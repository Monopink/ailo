# 离线消息接口

离线消息用于在客户端断联期间补齐未接收的消息，不提供历史同步能力。

## 语义边界：Offline vs History

- Offline（本文档）用于断线重连后的增量补齐，目标是确保该设备不丢消息（at-least-once + 客户端落盘后 ACK 推进游标）。
- History（未来能力）用于回看/补历史，按 conversation + 时间窗/分页，基础时间段可配置，付费可扩展更长时间；不在本文档范围。

## 接口列表

- [离线消息拉取](#离线消息拉取) - `GET /api/v1/messages/offline`
- [离线消息ACK](#离线消息ack) - `POST /api/v1/messages/ack`

---

## 离线消息拉取

### 基本信息

- **路径**: `GET /api/v1/messages/offline`
- **认证**: Bearer Token（必需）
- **说明**: 仅返回当前客户端尚未 ACK 的消息

### 请求参数

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| device_id | string | 是 | 设备/安装级 UUID（与 LeanCloud client_id 无关） |
| limit | integer | 否 | 单次返回条数（默认 100，上限 100，服务端会裁剪） |
| cursor | string | 否 | 分页游标（服务端返回） |

### 成功响应 (200)

```json
{
  "server_time_ms": 1710001112000,
  "limit": 100,
  "has_more": false,
  "next_cursor": null,
  "messages": [
    {
      "msg_id_server": "msg_273338979288485888",
      "msg_id_client": "client_abc",
      "conversation_id": "conv_272638151019859968",
      "from_qiao_id": "qiao_friendly_buddy_001",
      "to_qiao_id": "qiao_user001",
      "content": "你好",
      "message_type": 1,
      "client_sent_time_ms": null,
      "sent_time_ms": 1710001111333,
      "metadata": {
        "action": null,
        "notification_type": null
      }
    }
  ]
}
```

### 错误响应

**400 Bad Request**:

- `"参数错误"` - 参数缺失、格式错误或游标非法
- `"操作异常"` - 请求数据与当前登录态不匹配

**401 Unauthorized**:

- `"认证失效，请重新登录"` - Token 无效或已过期

**500 Internal Server Error**:

- `"系统错误（error_code）"` - 服务器内部错误

### 业务说明

- 新客户端首次请求会初始化游标并返回空列表（不做离线消息补齐）。
- 返回“该 device 尚未 ACK 的时间线增量”（双向：user↔assistant），用于多设备一致的聊天时间线。
- 消息集合仅包含聊天时间线消息（TEXT + CHAT_INFO）；NOTIFICATION 不属于聊天时间线，不在该接口返回范围内。
- 不提供历史同步能力；未 ACK 的消息会重复下发直到确认。
- 游标维度为 (user_id, device_id)；同一 device_id 可被多个账号复用。
- 服务端必须校验消息所属 `conversation_id` 对当前用户可见（例如联系人关系/会话参与方校验）；禁止仅依赖 `device_id` 过滤，避免越权或串会话。
- 分页排序规则：`sent_time_ms` 升序，`msg_id_server` 作为同一时间的稳定排序键。
- `next_cursor` 为本页最后一条消息的游标；`has_more=true` 时继续传 `cursor` 拉取下一页。
- 所有时间戳字段为 Unix 毫秒时间戳（UTC）。
- `sent_time_ms` 为服务端认定的事件时间（用于排序与游标推进）；`client_sent_time_ms` 仅为客户端上送时间（用于展示/调试）。
- 客户端按 `msg_id_server` 去重；`msg_id_client` 仅用于入站幂等与发送瞬间的本地对齐。
- Offline 仅用于断线重连后的补齐（在线多端同步应由消息通道完成）。

---

## 离线消息ACK

### 基本信息

- **路径**: `POST /api/v1/messages/ack`
- **认证**: Bearer Token（必需）
- **说明**: 客户端确认已保存消息，服务端推进游标

### 请求体

```json
{
  "device_id": "device_uuid",
  "last_ack_msg_id": "msg_273338979288485888"
}
```

### 成功响应 (200)

```json
{
  "success": true,
  "server_time_ms": 1710001112000
}
```

### 错误响应

**400 Bad Request**:

- `"参数错误"` - 参数缺失或格式错误
- `"操作异常"` - `last_ack_msg_id` 不存在或不属于当前用户

**401 Unauthorized**:

- `"认证失效，请重新登录"` - Token 无效或已过期

**500 Internal Server Error**:

- `"系统错误（error_code）"` - 服务器内部错误

### 业务说明

- ACK 适用于实时消息与离线消息。
- 服务端只在收到 ACK 后推进游标，避免丢失消息。
- 客户端必须在离线补偿拉取完成且消息已落盘后再发送 ACK。
- 断线重连后优先拉取离线消息，未完成补偿前不得发送 ACK。
- ACK 游标必须基于客户端已持久化的最大 (sent_time_ms, msg_id_server)。
- 如果 ACK 小于当前游标，忽略并记录 warning 日志。
- 如果 `last_ack_msg_id` 不存在或不属于当前用户，返回 `400 Bad Request`。
- 服务端以 `msg_id_server` 对应消息的 `sent_time_ms` 为准推进游标。
