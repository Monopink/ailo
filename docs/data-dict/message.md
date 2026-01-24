# 消息

管理消息历史记录和投递失败记录。

## message_history

消息历史记录表。

```txt
id -- Snowflake ID
direction -- 消息方向：1=inbound, 2=outbound
conversation_id -- 对话ID，关联contacts.conv_id
msg_id_server -- msg_+(Snowflake字符串)，外部使用，发送消息使用
msg_id_provider_inbound -- 第三方入站消息ID（LeanCloud `msgId`）
msg_id_provider_outbound -- 第三方出站确认ID，发送成功后回填
msg_id_client -- 客户端消息ID，接收消息使用
client_sent_time -- 消息中包含的客户端发送时间
from_type -- 发送方类型：1=user, 2=ai, 3=admin, 4=system
from_id -- 发送方内部ID
from_qiao_id -- 发送方外部ID
to_type -- 接收方类型：1=user, 2=ai, 3=admin, 4=system
to_id -- 接收方内部ID
to_qiao_id -- 接收方外部ID
service_provider -- 服务提供商：1=internal, 2=leancloud
message_type -- 消息类型（见 docs/spec/message/special-types.md）
content -- 消息内容
status -- 消息状态（见 docs/spec/message/schema.md）
message_metadata -- 消息元数据JSON
created_at
```

## message_delivery_failures

消息投递失败记录表，成功重发后删除记录。

```txt
id -- Snowflake ID
msg_id_server -- 原消息ID，关联message_history.msg_id_server
from_id -- 发送方内部ID
from_qiao_id -- 发送方外部ID
from_type -- 发送方类型：1=user, 2=ai, 3=admin, 4=system
to_id -- 接收方内部ID
to_qiao_id -- 接收方外部ID
to_type -- 接收方类型：1=user, 2=ai, 3=admin, 4=system
service_provider -- 服务提供商：1=internal, 2=leancloud
message_type -- 消息类型：1=text, 2=typing, 3=typing_end, 4=system
content -- 消息内容
fail_reason_code -- 失败原因代码
fail_detail -- 详细错误信息/堆栈，TEXT类型
retry_count -- 重试次数，默认0
max_retry_count -- 最大重试次数，默认3
next_retry_at -- 下次重试时间
created_at
updated_at
```

## message_offline_cursor

```txt
id -- Snowflake ID
user_id -- 用户ID（内部）
user_qiao_id -- 用户外部ID
device_id -- 设备/安装级 UUID
last_ack_msg_id -- 最近一次已确认的消息ID（msg_id_server）
last_ack_sent_at -- 最近一次已确认消息的服务端发送时间（毫秒时间戳）
last_pull_at -- 最近一次拉取离线消息时间
created_at
updated_at
```
