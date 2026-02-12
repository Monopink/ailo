# 资料系统

管理用户、AI、官方账号的公开资料和变更日志。

## profiles

统一资料表，管理用户、AI、官方账号的公开资料。

```txt
id -- Snowflake ID
owner_id -- 所有者内部ID
owner_qiao_id -- 所有者外部ID（全局唯一，每个 qiao_id 只能有一个 profile）
owner_type -- 所有者类型：1=user (包括所有用户类型: normal, official, virtual), 2=ai_persona (AI实例原型，被多个instance共享), 3=ai_instance (仅限管理员手动创建的instance)
nickname -- 昵称
gender -- 性别：1=male, 2=female, 3=other, 4=unknown
avatar_key -- 头像对象键（例如 avatars/2025/12/xxx.webp），仅在用户上传头像后写入；NULL 时由后端通过 CDN 默认图兜底
avatar_media_id -- 头像媒资记录ID，外键关联 media_files.id（保留最近一次确认头像的审计记录，NULL 表示使用默认头像）
avatar_prompt -- 头像描述，用于AI对话时的 prompt 替换
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
owner_type -- 所有者类型：1=user, 2=ai_persona, 3=ai_instance
modified_by_type -- 修改者类型：1=user, 2=admin, 3=system
field_name -- 修改的字段名，例如 nickname, avatar_key, bio
old_value -- 旧值
new_value -- 新值
change_reason -- 修改原因（例如用户提交、管理员修改）
created_at
```
