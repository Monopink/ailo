# 备份

数据库备份任务记录表，记录每次备份的执行状态与产物信息。

## backup_jobs

```txt
id -- 自增ID
status -- 状态（enum: BackupJobStatus）
started_at -- 开始时间
finished_at -- 结束时间
duration_ms -- 耗时毫秒
backup_file_name -- 文件名（db-YYYYMMDD-HHMMSS.sql.gz）
object_key -- COS 对象键（主备份文件）
bucket_name -- 备份桶名
storage_region -- 备份桶地域
file_size -- 文件大小（字节）
sha256 -- 校验值（主备份文件 SHA-256）
etag -- 对象 ETag（仅记录，不用于一致性校验，可空）
error_message -- 失败原因（TEXT，可空）
created_at
updated_at
```

旁路校验文件对象键固定为：`object_key + ".sha256"`。
