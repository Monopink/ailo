# 资料系统

管理用户、AI、官方账号的公开资料和变更日志。

## profiles

统一资料表，管理用户、AI、官方账号的公开资料。

```txt
id -- Snowflake ID
owner_id -- 所有者内部ID
owner_qiao_id -- 所有者外部ID（全局唯一，每个 qiao_id 只能有一个 profile）
owner_type -- 所有者类型：1=user (包括所有用户类型: normal, official, virtual), 2=ai_persona (AI角色原型，被多个instance共享), 3=ai_instance (仅限管理员手动创建的instance)
nickname -- 昵称
gender -- 性别：1=male, 2=female, 3=other
avatar_file_id -- 头像文件ID，关联media_files.id（自定义头像）
avatar_url -- 头像URL（客户端预设：assets://1234；云端：https://...）
avatar_prompt -- 头像描述，用于AI生成头像的占位符覆盖
bio -- 个人简介
region -- 地区
created_at
updated_at
```

## user_profile_logs

用户资料变更日志表，只存储用户资料变更记录。

```txt
id -- Snowflake ID
owner_id -- 所有者内部ID
owner_qiao_id -- 所有者外部ID
owner_type -- 所有者类型：1=user (包括所有用户类型: normal, official, virtual), 2=ai_persona (AI角色原型，被多个instance共享), 3=ai_instance (仅限管理员手动创建的instance)
modified_by_type -- 修改者类型：1=user, 2=admin, 3=system
field_name -- 修改的字段名，例如 nickname, avatar_url, bio
old_value -- 旧值
new_value -- 新值
change_reason -- 修改原因（例如用户提交、管理员修改）
created_at
```
