# 生产数据库备份实施计划（宿主机主控）

## 已确认决策

- 生产地域基线为腾讯云上海：`ap-shanghai`。
- 生产环境为腾讯云 `CVM`。
- PostgreSQL 继续运行在同机 Docker 容器中。
- 数据库备份执行主控放在宿主机，不放在 `backend` 容器。
- 系统层调度使用 `systemd timer`。
- 备份窗口固定为宿主机本地时区每日两次：`03:30`、`12:30`。
- 备份桶与媒体桶分离。
- 备份上传使用 boto3（S3 兼容）直连 COS，不引入 `coscli`。
- COS 备份桶开启 `SSE-COS` 默认加密。
- 保留策略固定为：`7天标准 + 8-30天低频 + 31-90天删除`。
- 本地短期保留固定为 7 天。
- 备份执行记录落库为最小表 `backup_jobs`。
- 备份通知系统本期不开发。
- 当前失败信息写入 `backup_jobs`、应用日志与系统日志（syslog）。
- 管理后台本期仅做“可见（监测）”，不提供任何触发能力。
- 恢复目标为“恢复到最近一次成功备份”，本期不做 PITR/WAL 归档。
- 恢复演练本期仅做方向规划，不进入实施范围。
- COS endpoint 基线为服务域名：`https://cos.<region>.myqcloud.com`（禁止使用桶域名作为 endpoint）。
- 宿主机备份链路不复用 backend 上传实现；宿主机脚本独立使用 boto3 进行上传与校验。
- 本计划依赖 `docs/plans/2026-03-12-storage-config-refactor-plan.md` 先完成。

## 目标

- 落地生产数据库自动备份链路。
- 落地 COS 备份桶上传、加密校验与生命周期策略。
- 落地宿主机执行记录写库能力。
- 落地管理后台的备份状态查询（监测）链路。
- 落地可观测性基线：systemd/journald + syslog 的排障路径明确。

## 涉及范围

- `backend/database/init/sql/01_schema.sql`
- `backend/app/models/backup.py`
- `backend/app/models/__init__.py`
- `backend/app/admin/views/backup_views.py`
- `backend/app/admin/views/__init__.py`
- `backend/app/admin/main.py`
- `backend/app/api/admin/__init__.py`
- `backend/app/crud/__init__.py`
- `docs/data-dict/backup.md`
- `deployment/prod/compose.yaml`
- `deployment/prod/.env.example`
- `deployment/prod/scripts/backup_db.py`
- `deployment/prod/scripts/cleanup_backup_records.py`
- `deployment/prod/systemd/*.service`
- `deployment/prod/systemd/*.timer`

## 架构基线

### 一、执行主体

- `systemd timer` 在宿主机触发数据库备份。
- 宿主机脚本直接执行 `docker exec -u postgres postgres pg_dump ...`。
- 备份压缩、校验、COS 上传、本地清理全部由宿主机脚本完成。
- 宿主机脚本直接连接业务数据库写入 `backup_jobs`。
- backend 仅负责查询 `backup_jobs` 与展示监测信息，不参与备份执行。

### 二、记录来源

- `backup_jobs` 是备份执行结果的主记录源。
- 当数据库连接可用时，宿主机脚本必须写入或更新 `backup_jobs`。
- 当数据库连接不可用时，宿主机脚本仅写 syslog 与本地日志，不增加本地补偿队列。
- 管理后台仅展示已成功落库的记录。

### 三、通知边界

- 本期不实现统一通知通道。
- 备份成功或失败事件不调用 backend 通知分发能力。
- 宿主机脚本始终写 syslog。
- backend 仅负责应用日志中的查询与展示链路。

## 数据库表设计

### backup_jobs

```txt
id -- 自增ID
status -- 状态：1=running, 2=success, 3=failed
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

索引：

- `idx_backup_jobs_started_at`（`started_at`）
- `idx_backup_jobs_status`（`status`）
- `idx_backup_jobs_created_at`（`created_at`）

保留策略：

- 仅保留 90 天内记录。
- 每周独立清理一次 `created_at < NOW() - INTERVAL '90 days'` 的历史记录。

## 对象命名与目录

- 宿主机本地备份目录：`/opt/ailo-prod/backups/database`
- 宿主机锁文件：`/run/lock/ailo-db-backup.lock`
- 宿主机备份脚本 venv：`/opt/ailo-prod/venv/ailo-backup`
- 本地文件名：`db-YYYYMMDD-HHMMSS.sql.gz`
- COS 对象键：`db-backups/YYYY/MM/db-YYYYMMDD-HHMMSS.sql.gz`
- COS 校验文件对象键：`db-backups/YYYY/MM/db-YYYYMMDD-HHMMSS.sql.gz.sha256`

## 执行链路

### 一、自动备份

1. `systemd timer` 在 `03:30`、`12:30` 触发宿主机备份脚本
2. 宿主机脚本获取文件锁
3. 宿主机脚本执行 `docker exec -u postgres postgres pg_dump`
4. 宿主机脚本生成 `.sql.gz`
5. 宿主机脚本生成 `sha256`
6. 宿主机脚本使用 `TENCENT_COS_BACKUP_*` 上传 COS
7. 宿主机脚本上传旁路校验文件：`db-YYYYMMDD-HHMMSS.sql.gz.sha256`
8. 宿主机脚本通过 `head_object()` 校验对象大小；若响应包含 `ServerSideEncryption` 字段，则要求为 `AES256`（对应 COS 的 `SSE-COS`）；ETag 仅记录不作为一致性校验依据
9. 宿主机脚本写入 `backup_jobs`
10. 宿主机脚本清理 7 天前的本地备份文件
11. 宿主机脚本释放文件锁

### 二、互斥与重入

- 备份脚本使用宿主机锁文件控制互斥。
- 锁已被持有时，本次执行立即失败并记录 `backup_in_progress`。
- 任何退出路径都必须释放文件锁。

### 三、本地保留清理

- 清理时机：备份成功完成后执行。
- 清理规则：删除修改时间早于 7 天前的本地备份文件。
- 清理位置：`/opt/ailo-prod/backups/database`

## COS 基线

### 一、生命周期

- 0-7 天：标准存储
- 8-30 天：低频存储
- 31-90 天：删除

### 二、加密

- COS 备份桶默认加密为 `SSE-COS`
- 上传请求携带 `ServerSideEncryption=AES256`；若响应包含 `ServerSideEncryption` 字段，则要求为 `AES256`

### 三、权限

- 备份凭据与媒体凭据分离
- 备份凭据仅拥有备份桶的上传、读取、列举权限
- 备份访问统一使用 HTTPS

## 管理后台边界

后台可见能力：

- 最近备份时间
- 最近备份结果
- 备份耗时
- 备份文件名
- 备份文件大小
- 备份校验值

后台可控能力：无（本期只读监测）

后台不提供能力：

- 编辑 `systemd timer` 表达式
- 展示备份密钥明文

## 恢复演练基线

本期仅做方向规划，先明确演练边界与验收口径，不进入实施：

- 演练恢复目标为临时数据库或临时容器。
- 演练不得覆盖生产数据库。
- 演练验收项（暂定方向）：备份可下载、可导入、基础连通性与关键表记录数可检查。

## 实施顺序

### 阶段 1：配置基线完成

1. 完成 `docs/plans/2026-03-12-storage-config-refactor-plan.md`
2. 完成 deployment 命名与镜像基线对齐
3. 验证媒体与备份配置已分域

### 阶段 2：数据库表与模型

1. 在 `backend/database/init/sql/01_schema.sql` 中新增 `backup_jobs`
2. 创建 `backend/app/models/backup.py`
3. 在 `backend/app/models/__init__.py` 注册模型
4. 同步 `docs/data-dict/backup.md`

### 阶段 3：宿主机备份脚本

1. 创建 `deployment/prod/scripts/backup_db.py`
2. 实现文件锁
3. 实现 `docker exec -u postgres postgres pg_dump`
4. 实现压缩、校验、COS 上传
5. 实现 `backup_jobs` 写库
6. 实现本地保留清理

### 阶段 4：宿主机记录清理脚本

1. 创建 `deployment/prod/scripts/cleanup_backup_records.py`

### 阶段 5：系统层调度

1. 创建自动备份 `systemd service` 与 `timer`
2. 创建备份记录清理 `systemd service` 与 `timer`
3. 启用并验证 `timer`

### 阶段 6：后台页面（只读监测）

1. 增加 `backup_jobs` 的 Starlette-Admin ModelView

## 验证清单

- 每日两次备份按时执行
- 宿主机本地目录生成 `.sql.gz` 备份文件
- COS 备份桶存在对应对象
- COS 对象加密状态字段存在时为 `ServerSideEncryption=AES256`
- `backup_jobs` 正确记录成功与失败结果
- 本地 7 天短保留生效
- 90 天历史记录清理生效
- 管理后台可查询备份记录
- systemd/journald 与 syslog 可定位并排障
