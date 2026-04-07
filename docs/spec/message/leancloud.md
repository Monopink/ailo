# LeanCloud 集成

本文档定义 LeanCloud 作为消息传输 Provider 的目标架构。

## 架构设计

LeanCloud 仅承担传输职责，业务状态与业务路由保持在服务端领域模型中。

### 设计原则

- LeanCloud 只负责消息传输，不承载业务逻辑
- 使用全局唯一系统会话（service conversation）
- 客户端通过单一 Bootstrap 接口获取建连所需全部数据
- 服务端负责会话有效性、用户订阅、签名、Presence 一次编排

说明：

- 消息传输层支持多个 Provider：LeanCloud（本文件）与 WebSocket（见 `websocket.md`）。
- 不同 Provider 的传输格式不同，但服务端统一转换为内部 `InboundMessageEvent`（见 `schema.md`）。
- LeanCloud 场景 dispatch 使用 USER 粒度 endpoint；`target_key` 对应 LeanCloud `client_id`（当前等同 `qiao_id`）。

## 客户端接入（Bootstrap 编排）

### 接口

- `POST /api/v1/lc-im/bootstrap`
- 详细契约见 [api/leancloud-message.md](../../api/leancloud-message.md#会话引导bootstrap)

### 服务端编排步骤

1. 读取并校验 LeanCloud 运行配置。
2. 校验系统会话 `im_conv_id` 存在且可用。
3. 确保当前用户已订阅系统会话（subscriber upsert）。
4. 生成登录签名。
5. upsert USER endpoint 并续租 Presence。
6. 返回完整建连参数与 `config_version`。

### 客户端强约束

- 仅使用 Bootstrap 响应初始化 SDK。
- 禁止本地硬编码 `app_id/app_key/server_url/im_conv_id`。
- `config_version` 变化时必须重建连接并清理会话缓存。
- 禁止“config + signature + presence”分步流程。

## 系统会话

所有 LeanCloud 消息都在系统会话发送：

- 对话 ID 存储在 `system_configs.leancloud_im_service_conversation_id`
- Webhook 入站校验 `conv.objectId` 必须与当前生效系统会话一致
- 会话不可用时，Bootstrap 必须失败并返回系统错误（禁止降级/回退）

## Webhook 处理

### 接口定义

完整接口定义见 [api/leancloud-message.md](../../api/leancloud-message.md#leancloud-消息-webhook)

- 路径：`POST /api/v1/leancloud/webhook/{webhook_token}`

### 外层结构示例

```json
{
  "msgId": "nYH9iBSBS_uogCEgvZwE7Q",
  "conv": { "objectId": "69c1113b1dc6aa415111cc49" },
  "from": "qiao_user001",
  "data": "{...}",
  "timestamp": 1710001111333,
  "ack": true
}
```

### 关键字段

- `msgId`：LeanCloud 消息 ID，写入 `msg_id_provider_inbound`
- `conv.objectId`：LeanCloud 系统会话 ID，必须匹配服务端当前配置
- `data`：TypedMessage JSON（解析 `_lcattrs`）
- `from`：发送方 `client_id`

### 处理流程

1. 校验 `webhook_token`
2. 校验 `conv.objectId`
3. 解析 `data` 到 `_lcattrs`
4. 映射到 `InboundMessageEvent`
5. 调用统一消息处理管线
6. 返回 `{ "code": 200 }`

### 重复消息处理

按 `msgId` 在 `message_history.msg_id_provider_inbound` 去重：

- 已存在：幂等丢弃并返回成功
- 不存在：进入正常处理

## 消息发送

### 发送流程

1. dispatch 选择 provider=LeanCloud 的活跃 USER endpoint
2. 使用 endpoint `target_key`（client_id）组装 `to_clients`
3. 构建 TypedMessage payload
4. 调用 LeanCloud REST API
5. 写入 `message_deliveries.provider_msg_id`

### Typing（transient）

- `message_type=2|3`（TYPING_START / TYPING_END）为 best-effort realtime 事件
- LeanCloud 发送时必须设置 `transient=true`

### `_lcattrs` 出站字段

- `msg_id`：时间线消息 `msg_id_server`
- `msg_id_client`：可选；入站用户消息回传原客户端 ID
- assistant/系统消息可省略 `msg_id_client`

## 配置管理

### system_configs

- `leancloud_im_server_url` - LeanCloud 服务地址
- `leancloud_im_service_conversation_id` - 系统会话 ID
- `leancloud_im_webhook_token` - Webhook 令牌
- `api_base_url` - API 基础地址（用于拼接 Webhook URL）

### 密钥边界

- `master_key` 仅允许服务端持有，禁止下发客户端。
- `app_key` 用于客户端 SDK 建连参数，不作为服务端机密边界。

## 发送错误

- 网络错误：写入 `message_deliveries`（failed/pending）进入重试
- LeanCloud 异常：写入 `message_deliveries`（failed/pending）进入重试
- 载荷格式错误：记录日志并告警，不重试

详见 [failure-handling.md](failure-handling.md)
