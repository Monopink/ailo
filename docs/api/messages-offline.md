# 离线消息接口

离线消息用于在客户端断联期间补齐未接收的消息，不提供历史同步能力。

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
      "conv_id": "conv_272638151019859968",
      "from_qiao_id": "qiao_friendly_buddy_001",
      "to_qiao_id": "qiao_user001",
      "content": "你好",
      "message_type": 1,
      "sent_time": 1710001111222,
      "server_time": 1710001111333,
      "action": null,
      "notification_type": null,
      "data": null
    }
  ]
}
```

### 业务说明

- 新客户端首次请求会初始化游标并返回空列表（不做离线消息补齐）。
- 仅返回 **发给当前用户** 的消息（to_qiao_id == current user）。
- 不提供历史同步能力；未 ACK 的消息会重复下发直到确认。
- 分页排序规则：`sent_time` 升序，`msg_id_server` 作为同一时间的稳定排序键。
- `next_cursor` 为本页最后一条消息的游标；`has_more=true` 时继续传 `cursor` 拉取下一页。
- 所有 *_time 字段为 Unix 毫秒时间戳（UTC）。

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
  "last_ack_msg_id": "msg_273338979288485888",
  "last_ack_sent_at": 1710001111333
}
```

### 成功响应 (200)

```json
{
  "success": true,
  "server_time_ms": 1710001112000
}
```

### 业务说明

- ACK 适用于实时消息与离线消息。
- 服务端只在收到 ACK 后推进游标，避免丢失消息。
- 客户端必须在离线补偿拉取完成且消息已落盘后再发送 ACK。
- 断线重连后优先拉取离线消息，未完成补偿前不得发送 ACK。
- ACK 游标必须基于客户端已持久化的最大 (sent_time, msg_id_server)。
- 如果 ACK 小于当前游标，忽略并记录 warning 日志。
- 服务端以 `msg_id_server` 对应的 `sent_time` 为准，若客户端 `last_ack_sent_at` 不一致仅记录 warning。
- 服务端会将对应消息状态更新为 delivered（不引入 read 状态）。
