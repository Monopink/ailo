# 消息

本文档描述消息系统相关的数据表。

---

## message_history

消息事实表：记录“谁在什么时间向谁发送了什么内容”。该表不承载投递状态。

```txt
id -- Snowflake ID
direction -- 消息方向：1=inbound, 2=outbound
conversation_id -- 对话ID，关联 contacts.conversation_id
msg_id_server -- 服务端生成的时间线消息ID
msg_id_client -- 客户端消息ID
msg_id_provider_inbound -- 第三方入站消息ID
inbound_provider -- 入站 Provider
inbound_device_id -- 入站 device_id
client_sent_at -- 客户端上送的发送时间
sent_at -- 服务端认定的发送/事件时间
from_type -- 发送方类型
from_id -- 发送方内部ID
from_qiao_id -- 发送方外部ID
to_type -- 接收方类型
to_id -- 接收方内部ID
to_qiao_id -- 接收方外部ID
message_type -- 消息类型
content -- 消息内容
message_metadata -- 消息元数据 JSON
llm_request_id -- 关联 ai_request_logs.id
created_at
```

---

## message_devices

设备游标表：管理 (user_id, device_id) 维度的离线游标与活跃信息。

```txt
id -- Snowflake ID
user_id -- 用户ID（内部）
user_qiao_id -- 用户外部ID
device_id -- 设备/安装级 UUID
last_acked_msg_id -- 最近一次已确认的消息ID
last_acked_msg_sent_at -- 最近一次 ACK 对应消息的 sent_at
last_pull_at -- 最近一次拉取离线消息时间
last_seen_at -- 最近一次在线/心跳时间
created_at
updated_at
```

---

## message_endpoints

端点表：管理“可投递端点”（provider 绑定 + lease）。
该表支持两种 endpoint 粒度：USER（用户级）与 DEVICE（设备级）。

```txt
id -- Snowflake ID（endpoint_id）
user_id -- 用户ID（内部）
user_qiao_id -- 用户外部ID
endpoint_scope -- 端点粒度：1=USER, 2=DEVICE
device_id -- 设备 UUID
provider -- 统一使用传输 Provider 枚举
target_key -- Provider 的可投递标识
client_kind -- 端类型：web/miniprogram/ios/android
lease_expires_at -- endpoint 活跃到期时间
last_seen_at -- 最近一次在线/续租时间
created_at
updated_at
```

---

## message_deliveries

投递记录表：按 endpoint 维度记录投递状态与失败原因。

```txt
id -- Snowflake ID（delivery_id）
msg_id_server -- 关联 message_history.msg_id_server
endpoint_id -- 关联 message_endpoints.id
provider -- Provider
target_key -- 冗余存储目标标识
provider_msg_id -- 第三方回执 ID（可为空）
status -- 投递状态
dispatched_at -- provider 投递成功时间（不等于客户端 HTTP ACK）
failed_reason_code -- 失败原因代码
failed_detail -- 失败详情/堆栈（TEXT）
created_at
updated_at
```

---

## message_dispatch_outbox

派发任务表：记录“消息事实已提交、待派发”的任务，用于重试与故障恢复。

```txt
id -- Snowflake ID
outbox_type -- 任务类型：1=TIMELINE_FANOUT
msg_id_server -- 关联 message_history.msg_id_server
owner_user_id -- 任务所属用户（用于查询目标 endpoints）
status -- 任务状态：1=pending, 2=processing, 3=done, 4=failed
attempt_count -- 已重试次数（不含首次派发）
next_retry_at -- 下次可重试时间
locked_at -- 当前处理锁定时间
last_error_code -- 最近一次错误码
last_error_detail -- 最近一次错误详情
created_at
updated_at
```
