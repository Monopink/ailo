# 权益与配额（未来）

## user_entitlements（选用）

用户权益扩展表。如果奖励是“联系人栏位 +1”这类功能性权益，可以直接存在 quota 表里，或者单独建一张 user_entitlements。

```txt
id
user_id
entitlement_type -- contact_slots, search_limit, ai_clone, etc.
value            -- 当前值（默认值 + 奖励值）
source           -- invite, subscription, purchase
expire_at        -- NULL 表示永久
updated_at
```

目标：

- 统一管理用户的功能权益（不限于邀请奖励），与订阅、商城购买逻辑兼容。

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
