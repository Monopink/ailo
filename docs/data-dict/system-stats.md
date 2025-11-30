# 统计报表

管理用户、收入、消息、AI等统计数据（按日/周/月）。

## stats_user_daily/weekly/monthly

用户统计表（按日/周/月）。每天凌晨统计daily数据，周一凌晨统计weekly数据，每月1日凌晨统计monthly数据。

```txt
id -- 自增ID
stat_date -- 统计日期
total_users -- 总用户数
new_users -- 新增用户数
active_users -- 活跃用户数
subscriptions -- 总订阅用户数
new_subscriptions -- 新订阅用户数
canceled_subscriptions -- 退订用户数
created_at
```

## stats_revenue_daily/weekly/monthly

收入统计表（按日/周/月）。

```txt
id -- 自增ID
stat_date -- 统计日期
total_revenue -- 总收入
orders_count -- 订单数量
avg_order_amount -- 平均订单金额
refund_amount -- 退款金额
created_at
```

## stats_message_daily/weekly/monthly

消息统计表（按日/周/月）。

```txt
id -- 自增ID
stat_date -- 统计日期
total_messages -- 总消息数
avg_messages_per_user -- 人均消息数
active_conversations -- 活跃对话数
created_at
```

## stats_ai_daily/weekly/monthly

AI统计表（按日/周/月）。

```txt
id -- 自增ID
stat_date -- 统计日期
ai_personas -- Persona 总数
active_ai_personas -- 活跃 Persona 数
ai_requests_count -- 请求总数
avg_ai_requests_per_user -- 人均请求数
created_at
```
