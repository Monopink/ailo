# 存储系统

统一管理所有由客户端或后台上传的媒资文件，负责对象存储的元数据、访问控制与审计。当前仅 `media_files` 一张表，但会与 `profiles`、`contacts` 等核心表通过外键或业务约束关联。

## media_files

```txt
id -- Snowflake ID
file_id -- file_+Snowflake，外部引用ID（URL、API返回统一使用此字段）
file_type -- 文件类型（enum: FileType）
category -- 二级分类标签（可空），用于后续业务分组
storage_provider -- 存储提供方：tencent_cos
bucket_name -- 对象存储桶名称
object_key -- 存储对象键：{type}/{year}/{month}/{snowflake}.{ext}
storage_region -- 存储地域（COS 场景使用）
original_name -- 用户上传时的原始文件名
file_size -- 文件大小（字节）
mime_type -- MIME 类型
file_hash -- SHA-256 摘要，用于同一用户去重
is_public -- 是否公开可直接访问（头像类为 true）
upload_by_type -- 上传者类型（enum: UploaderType）
upload_by_id -- 上传者内部ID（admin/system 可为空）
upload_by_qiao_id -- 上传者外部ID，用于审计
etag -- 对象存储返回的 ETag，用于校验
confirmed_at -- 文件被确认可用的时间（代理上传即时写入）
confirmed_by_id -- 审核或确认人ID，默认记录上传者
status -- 文件状态（enum: FileStatus）
created_at -- 记录创建时间（默认 NOW()）
updated_at -- 记录更新时间（触发器自动维护）
```
