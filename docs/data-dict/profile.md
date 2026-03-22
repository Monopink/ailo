# 资料系统

管理用户、AI、官方账号的公开资料和变更日志。

## profiles

统一资料表，管理用户、AI、官方账号的公开资料。

```txt
id -- Snowflake ID
owner_id -- 所有者内部ID
owner_qiao_id -- 所有者外部ID（全局唯一，每个 qiao_id 只能有一个 profile）
owner_type -- 所有者类型（enum: ProfileOwnerType）
nickname -- 昵称
gender -- 性别（enum: Gender）
avatar_key -- 头像对象键（例如 avatars/2025/12/xxx.webp），仅在用户上传头像后写入；NULL 时由后端通过 CDN 默认图兜底
avatar_media_id -- 头像媒资记录ID，外键关联 media_files.id（保留最近一次确认头像的审计记录，NULL 表示使用默认头像）
avatar_prompt -- 头像描述，用于AI对话时的 prompt 替换
bio -- 个性签名
region -- 服务端生成的地区展示快照（规范见 docs/spec/client/base/profile-and-settings.md）
region_country_code -- 地区国家/地区代码（ISO 3166-1 alpha-2，当前仅使用 CN）
region_cn_city_code -- 中国大陆市级行政区划代码（6位字符串），仅当 region_country_code=CN 时写入
created_at
updated_at
```

## user_profile_logs

用户资料变更日志表，只存储用户资料变更记录。

```txt
id -- Snowflake ID
owner_id -- 所有者内部ID
owner_qiao_id -- 所有者外部ID
owner_type -- 所有者类型（enum: ProfileOwnerType）
modified_by_type -- 修改者类型（enum: ProfileModifierType）
field_name -- 修改的字段名，例如 nickname, avatar_key, bio
old_value -- 旧值
new_value -- 新值
change_reason -- 修改原因（例如用户提交、管理员修改）
created_at
```
