# 管理后台

管理后台管理员账户、操作日志和登录日志。

## admin_users

管理员用户表，存储后台管理员账户信息。

```txt
id -- 自增ID
username -- 管理员用户名，唯一
password_hash -- 密码哈希值
role -- 角色类型：1=super_admin, 2=admin, 3=viewer
status -- 账户状态：1=active, 2=inactive
last_login -- 最后登录时间
login_count -- 登录次数
created_by -- 创建者ID（admin_user_id或system）
created_at
updated_at
```

## admin_operation_logs

管理员操作日志表，记录所有管理员操作。

```txt
id -- 自增ID
admin_user_id -- 关联admin_users.id
operation_type -- 操作类型：1=CREATE, 2=UPDATE, 3=DELETE, 4=ENABLE, 5=DISABLE
resource_type -- 资源类型：1=user, 2=ai_persona, 3=config, 4=admin等
resource_id -- 资源ID
resource_name -- 资源名称
operation_desc -- 操作描述
ip_address -- 操作IP地址
user_agent -- 用户代理信息
created_at
```

## admin_login_logs

管理员登录日志表，记录管理员登录历史。

```txt
id -- 自增ID
admin_user_id -- 关联admin_users.id
username -- 登录用户名
user_agent -- 用户代理信息
ip_address -- 登录IP地址
result -- 登录结果：1=success, 2=fail
fail_reason -- 失败原因
created_at
```
