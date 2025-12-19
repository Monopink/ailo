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
avatar_file_id -- 头像文件ID，外键关联 media_files.id（仅用户上传头像，空值时后端返回 COS avatar/default.webp）
avatar_prompt -- 头像描述，用于AI对话时的 prompt 替换
bio -- 个人简介
region -- 地区
created_at
updated_at
```

### 初始化规则

- 新创建的用户会在手机号/微信登录阶段立刻生成 profile stub，字段以默认昵称、性别 unknown 填充。未上传头像时 `avatar_file_id` 为空，由后端根据 `TENCENT_COS_CDN_DOMAIN` / `TENCENT_COS_ENDPOINT` 返回 `avatar/default.webp`，确保任意接口都能获得可用的头像 URL。
- 当 `PUT /api/v1/user/profile` 成功写入资料后，对应 `users.needs_profile_setup` 会变为 0，同时 `profiles` 表保留最新头像、昵称、region 等信息，并追加一条 `user_profile_logs` 记录。

## user_profile_logs

用户资料变更日志表，只存储用户资料变更记录。

```txt
id -- Snowflake ID
owner_id -- 所有者内部ID
owner_qiao_id -- 所有者外部ID
owner_type -- 所有者类型：1=user, 2=ai_persona, 3=ai_instance
modified_by_type -- 修改者类型：1=user, 2=admin, 3=system
field_name -- 修改的字段名，例如 nickname, avatar_file_id, bio
old_value -- 旧值
new_value -- 新值
change_reason -- 修改原因（例如用户提交、管理员修改）
created_at
```
