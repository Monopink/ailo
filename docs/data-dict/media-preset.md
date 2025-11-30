# 媒体与预设资源

管理媒体文件和预设资源（头像、表情等）。

## media_files

媒体文件管理表，统一管理头像、表情、图片等资源。

```txt
id -- Snowflake ID
file_id -- file_+随机字符，外部使用
file_type -- 文件类型：1=avatar, 2=emoji, 3=image, 4=document
original_name -- 原始文件名
file_path -- 文件存储路径
file_url -- 文件访问URL
file_size -- 文件大小（字节）
mime_type -- MIME类型
upload_by_type -- 上传者类型：1=user, 2=admin, 3=system
upload_by_id -- 上传者ID
upload_by_qiao_id -- 上传者外部ID
status -- 文件状态：1=active, 2=inactive, 3=deleted
created_at
updated_at
```

## preset_assets

预设资源管理表，统一管理预设图片资源（头像、表情贴图等）和对应的AI提示词。

```txt
id -- Snowflake ID
asset_type -- 资源类型：1=avatar, 2=emoticon
name -- 资源唯一标识，4位随机数字，如"8923", "7452"（默认头像使用"default"）
category -- 分类
is_client_preset -- 是否客户端预设：1=yes, 0=no
file_id -- 关联media_files.id（云端预设资源，客户端预设为NULL）
url -- 资源URL（客户端预设：assets://1234；云端：https://...）
prompt -- AI提示词（用于AI生成内容时的描述）
description -- 资源描述（用于管理后台显示）
status -- 状态：1=active, 2=inactive
sort_order -- 排序顺序
created_at
updated_at
```
