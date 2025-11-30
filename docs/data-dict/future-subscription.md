# 2.0功能 - 订阅与权益系统

未来版本规划的订阅、钱包、邀请奖励等功能。

## user_invitations

用户邀请表。

```txt
id
inviter_id       -- 邀请人用户ID
inviter_qiaoid
invitee_id       -- 被邀请人用户ID（注册后绑定），注册前可以为NULL
invitee_qiaoid
invite_code      -- 邀请码
status           -- pending, accepted, registered, rewarded
created_at
updated_at
```

## invite_reward_rules

邀请奖励规则表，配置不同条件下的奖励内容。

```txt
id
event_type       -- 注册完成、新用户活跃7天、首单支付等
reward_type      -- contact_slot, points, quota, subscription_days
reward_value     -- 奖励数值（如1栏位、100积分、30天VIP）
status           -- active, inactive
created_at
updated_at
```

## invite_rewards

奖励发放记录表。

```txt
id
invitation_id    -- 对应 user_invitations
user_id          -- 获奖用户
reward_type      -- contact_slot, points, quota, subscription_days
reward_value
status           -- pending, granted, revoked
granted_at
created_at
updated_at
```

确保奖励发放有日志，不会丢单。支持"撤回奖励"（如用户作弊）。

## user_entitlements（选用）

用户权益扩展表，如果奖励是 联系人栏位 +1 这种功能性权益，可以直接存在 quota 表里，或者单独建一张 user_entitlements。

```txt
id
user_id
entitlement_type -- contact_slots, search_limit, ai_clone, etc.
value            -- 当前值（默认值 + 奖励值）
source           -- invite, subscription, purchase
expire_at        -- NULL 表示永久
updated_at
```

统一管理用户的功能权益（不限于邀请奖励），和订阅、商城购买逻辑兼容。

## subscription_plans

订阅计划表（待设计）。

## subscriptions

用户订阅表。

```txt
id
user_id
plan -- 等级写死
status -- active,expired,canceled,trial
start_date
end_date
auto_renew
created_at
updated_at
```

## wallets

用户钱包表。

```txt
id
user_id
currency_type -- 写死 points,coins,gems
balance
updated_at
```

## wallet_transactions

钱包交易记录表。

```txt
id
user_id
currency_type
change_amount -- 正数增加，负数扣除
balance_after -- 变动后的余额
reason_code -- 'purchase', 'reward', 'exchange', 'refund', 'system_adjustment'
metadata JSON -- 附加信息，比如订单号、活动ID
created_at
```

## quota

用户配额表。

```txt
id
user_id
quota_type -- 写死 chat_tokens
current_usage -- 已用量
total_value -- 配额上限
reset_cycle -- 重置周期
reset_at -- 下次重置时间
updated_at
```

## user_entitlements_summary

汇总表，方便查询总额。

```txt
id
user_id
entitlement_type   -- contact_slots
total_value        -- 汇总的有效上限（计算得出）
used_value         -- 已用量
updated_at
```

## user_entitlement_batches

批次表，精确记录每一份来源。

```txt
id
user_id
entitlement_type   -- contact_slots
value              -- 本批次数量 (+10, +5)
used_value         -- 本批次已使用量（可选）
source             -- invite, subscription, promotion, system
expire_at          -- NULL = 永久，否则到期时间
created_at
```

## quota_usage_log

配额使用日志表。

```txt
id
user_id
quota_type
reason_code -- 'chat', 'system_adjust', 'purchase_extra'
metadata
created_at
```

## orders

订单表，交易类表要使用事务。

```txt
id
user_id
order_no -- 订单编号
amount -- 金额
currency
pay_method -- wechat,apple,alipay
status -- pending,paid,failed,refunded
created_at
paid_at
```
