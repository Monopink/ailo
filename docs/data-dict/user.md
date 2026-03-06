# 用户体系

管理用户账户、认证令牌、第三方绑定和登录记录。

## users

用户基础信息表，存储用户账户数据。

```txt
id -- Snowflake ID
qiao_id -- qiao_+随机字符，外部使用，唯一标识
username -- 用户敲敲号，可选字段，NULL表示未设置；用户端首次设置成功后不可修改（管理端 super_admin/admin 可改）
phone -- 手机号(E.164格式)，用于登录验证，必填，唯一
email -- 邮箱地址
password_hash -- 密码哈希值
is_verified -- 是否实名验证：1=yes, 0=no
verified_at -- 实名认证通过时间
verify_source -- 实名验证来源（如公安三要素、支付宝、微信、腾讯云等）
verification_info -- 实名验证详细信息JSON存储
status -- 账户状态：1=active, 2=inactive, 3=suspended
needs_profile_setup -- 是否需要补全资料：1=true, 0=false；新创建用户默认为1，成功调用 `PUT /api/v1/user/profile` 后置为0
user_type -- 用户类型：1=normal, 2=official, 3=virtual
last_login -- 最后登录时间
created_at
updated_at
```

## user_tokens

用户令牌表（双Token 架构）：管理 Access Token 和 Refresh Token、设备限制与吊销。

```txt
id -- Snowflake ID
user_id -- 关联users.id
user_qiao_id -- 关联users.qiao_id，冗余字段便于查询
access_token -- Access JWT令牌（唯一）
device_type -- 设备类型：1=ios, 2=android, 3=web, 4=mini_program
device_id -- 设备唯一标识（UUID）
platform_info -- 平台信息（JSONB，可选）
ip_address -- 登录IP地址
user_agent -- UA信息
access_expires_at -- Access Token过期时间
status -- 令牌状态：1=active, 2=revoked
last_activity_at -- 最后活动时间
access_revoked_at -- Access Token吊销时间
refresh_token_hash -- Refresh Token 哈希值（SHA-256）
refresh_expires_at -- Refresh Token 过期时间
refresh_revoked_at -- Refresh Token 吊销时间
token_metadata -- 附加元数据（JSONB）：刷新计数、设备信息等
created_at
updated_at
```

## user_auths

第三方身份绑定表（仅存储身份映射，不保存登录会话与第三方长期令牌）。

```txt
id -- Snowflake ID
user_id -- 关联users.id
user_qiao_id -- 关联users.qiao_id，冗余字段便于查询
auth_type -- 授权平台类型：1=apple, 2=qq, 3=wechat
provider_uid -- 平台用户唯一ID（WeChat openid / Apple sub / 抖音 open_id / 支付宝 user_id）
unionid -- 跨应用统一ID（仅微信，可选）
app_id -- 平台应用标识（可选，用于多应用区分）
extra_data -- 附加信息（JSONB）
status -- 状态：1=active, 2=revoked
revoked_at -- 解绑时间（可选）
created_at
updated_at
```

## login_records

用户登录记录表，记录所有登录尝试。

```txt
id -- Snowflake ID
user_id -- 关联users.id
user_qiao_id -- 关联users.qiao_id
login_time -- 登录时间
login_type -- 登录方式：1=password, 2=sms, 3=wechat, 4=apple
platform -- 平台：1=ios, 2=android, 3=web, 4=mini_program
device_id -- 设备ID/标识（UUID）
ip_address -- 登录IP（兼容IPv6）
user_agent -- 浏览器/设备UA信息
result -- 登录结果：1=success, 2=fail
fail_reason -- 失败原因
user_token_id -- 关联 user_tokens.id（仅成功登录写入；失败为空）
created_at
```
