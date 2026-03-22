# 通知

管理通知推送历史记录。

## notification_push_history

通知推送历史表，记录所有发送的通知消息。

**说明**: 通知消息不存入 message_history，单独存储用于调试、分析和重试。

```txt
id -- Snowflake ID
to_qiao_id -- 接收者 qiao_id
notification_type -- 通知类型（enum: NotificationType）
action_data -- 操作数据（action + data），JSONB类型
status -- 状态（enum: NotificationStatus）
error_message -- 错误信息（失败时），TEXT类型
created_at
updated_at
```
