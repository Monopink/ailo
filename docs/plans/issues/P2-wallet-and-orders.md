# 钱包与订单（未来）

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
