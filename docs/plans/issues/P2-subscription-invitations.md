# 邀请与奖励（未来）

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

约束：

- 奖励发放需要可追溯日志，不丢单。
- 支持撤回奖励（例如作弊场景）。
