# 对象存储配置重构计划（MEDIA/BACKUP 分域）

## 已确认决策

- 对象存储配置拆分为媒体作用域与备份作用域。
- 媒体配置统一使用 `TENCENT_COS_MEDIA_*` 命名。
- 备份配置统一使用 `TENCENT_COS_BACKUP_*` 命名。
- dev、staging、prod 的 compose 服务命名基线统一为 `postgres`、`backend`、`nginx`、`certbot`。
- PostgreSQL 容器名统一为 `postgres`。
- backend 容器名统一为 `backend`。
- nginx 容器名统一为 `nginx`。
- PostgreSQL 镜像基线统一为 `postgres:18`。
- deployment 环境模板中的对象存储变量命名必须与后端配置模型完全一致。
- `TENCENT_COS_MEDIA_ENDPOINT` 与 `TENCENT_COS_BACKUP_ENDPOINT` 必须显式配置。
- COS endpoint 禁止默认拼接回退。
- 公开媒体 URL 的唯一权威来源为 `system_configs.media_public_base_url`。
- 公开媒体 URL 禁止环境变量回退。
- 缺失 `media_public_base_url` 时应用启动保持可用，相关 API 返回 5xx 且遵守 error_code 约定，不暴露实现细节。
- 备份上传仅允许使用 `TENCENT_COS_BACKUP_*` 初始化存储后端。
- 备份配置按需校验，仅在备份链路初始化时要求完整配置。

## 目标

- 消除当前单桶配置命名与目标设计不一致的问题。
- 统一媒体与备份的配置边界、初始化方式与错误行为。
- 为后续生产备份实施提供稳定的配置基线。

## 涉及范围

- `backend/app/core/config.py`
- `backend/app/services/storage/tencent_cos.py`
- `backend/app/services/storage/factory.py`
- `backend/app/services/media/config.py`
- `backend/app/services/profile/avatar.py`
- `backend/app/services/contact/service.py`
- `backend/app/services/media/uploader.py`
- `backend/app/main.py`
- `backend/app/admin/views/system_settings_view.py`
- `backend/app/admin/views/dashboard_view.py`
- `backend/app/admin/templates/custom_views/system_settings.html`
- `backend/tests/test_media_config.py`
- `deployment/compose.base.yaml`
- `deployment/dev/compose.yaml`
- `deployment/staging/compose.yaml`
- `deployment/prod/compose.yaml`
- `deployment/prod/.env.example`
- `deployment/staging/.env.example`
- `deployment/dev/.env.example`
- `deployment/prod/scripts/deploy.sh`
- `deployment/staging/scripts/deploy.sh`
- `deployment/prod/scripts/README.md`
- `deployment/staging/scripts/README.md`
- `docs/spec/storage.md`
- 相关引用上述配置项的接口文档与实现文档

## 重构基线

### 一、环境变量

媒体配置项：

- `TENCENT_COS_MEDIA_SECRET_ID`
- `TENCENT_COS_MEDIA_SECRET_KEY`
- `TENCENT_COS_MEDIA_REGION`
- `TENCENT_COS_MEDIA_BUCKET`
- `TENCENT_COS_MEDIA_ENDPOINT`

备份配置项：

- `TENCENT_COS_BACKUP_SECRET_ID`
- `TENCENT_COS_BACKUP_SECRET_KEY`
- `TENCENT_COS_BACKUP_REGION`
- `TENCENT_COS_BACKUP_BUCKET`
- `TENCENT_COS_BACKUP_ENDPOINT`

移除项：

- `TENCENT_COS_SECRET_ID`
- `TENCENT_COS_SECRET_KEY`
- `TENCENT_COS_REGION`
- `TENCENT_COS_BUCKET`
- `TENCENT_COS_ENDPOINT`
- `MEDIA_PUBLIC_BASE_URL`

### 二、运行时行为

- `get_settings()` 启动时必须校验所有必填媒体配置字段（不包含 `media_public_base_url`）。
- `TencentCOSBackend` 初始化时必须要求显式 `endpoint`。
- `TencentCOSBackend.get_public_url()` 仅用于显式传入 CDN 域名的场景，不参与媒体默认 URL 回退。
- `get_media_base_url()` 与 `refresh_media_base_url()` 仅允许读取 `system_configs.media_public_base_url`。
- 当 `system_configs.media_public_base_url` 缺失时，必须抛出平台配置异常，不返回空字符串，不回退到环境变量。
- 头像默认图 URL 与用户头像 URL 统一由 `system_configs.media_public_base_url + object_key` 生成。
- 应用启动流程捕获 `media_public_base_url` 缺失，不阻断启动；相关 API 返回 5xx，响应遵守 error_code 约定与通用文案规范。

### 三、初始化边界

- 媒体上传、头像 URL、媒体查询统一使用媒体配置。
- 备份上传链路单独创建备份存储后端，不复用媒体配置工厂。
- 任何业务路径不得读取备份凭据。
- 任何备份路径不得读取媒体凭据。
- 任何 API 层返回不得暴露配置 key 或实现细节。

### 四、deployment 基线

- `DB_HOST` 统一为 `postgres`。
- nginx `BACKEND_UPSTREAM` 统一为 `backend:8000`。
- deployment 脚本中的 compose service 名称必须与 compose 文件一致。
- staging 中历史遗留的 `postgres_staging`、`backend_staging`、`nginx_staging` 命名全部移除。
- prod 中历史遗留的 `postgres_db`、`postgres_db_container` 命名全部移除。
- staging 中 PostgreSQL 镜像从 `postgres:18-alpine` 统一为 `postgres:18`。
- 各环境 `.env.example` 仅保留实际接线的配置项。

## 实施顺序

### 阶段 1：配置模型重构

1. 更新 `backend/app/core/config.py`
2. 删除旧单桶变量定义
3. 新增 `TENCENT_COS_MEDIA_*` 与 `TENCENT_COS_BACKUP_*` 定义
4. 为媒体与备份 endpoint 增加显式必填校验

### 阶段 2：存储后端重构

1. 更新 `backend/app/services/storage/tencent_cos.py`
2. 删除 endpoint 默认拼接逻辑
3. 保持 `TencentCOSBackend` 仅负责 S3 兼容对象操作

### 阶段 3：媒体 URL 重构

1. 更新 `backend/app/services/media/config.py`
2. 删除环境变量回退逻辑
3. 更新 `backend/app/services/profile/avatar.py`
4. 保证缺失 `media_public_base_url` 时抛出配置异常
5. 更新 `backend/app/services/contact/service.py`，移除缺失配置时的空字符串回退
6. 调整 `backend/app/main.py` 启动流程，捕获缺失配置并记录错误，避免阻断启动
7. 更新 admin 视图与模板移除环境变量回退文案与展示

### 阶段 4：媒体调用链对齐

1. 更新 `backend/app/services/storage/factory.py`
2. 改为使用 `TENCENT_COS_MEDIA_*` 初始化媒体后端
3. 更新 `backend/app/services/media/uploader.py`
4. 修正媒体桶名与地域字段来源

### 阶段 5：deployment 基线对齐

1. 统一 `deployment/dev/compose.yaml`、`deployment/staging/compose.yaml`、`deployment/prod/compose.yaml` 的服务命名
2. 统一各环境 `DB_HOST=postgres`
3. 统一 staging nginx `BACKEND_UPSTREAM=backend:8000`
4. 统一 staging PostgreSQL 镜像为 `postgres:18`

### 阶段 6：部署模板与文档同步

1. 更新各环境 `.env.example`
2. 删除旧变量示例
3. 更新 deployment 脚本中的环境变量校验清单
4. 更新 deployment README 中的变量说明
5. 对齐 `docs/spec/storage.md`
6. 对齐引用旧变量名的文档
7. 更新 `backend/tests/test_media_config.py` 覆盖无回退与启动不阻断行为

## 验证清单

- 后端启动时不再读取旧单桶配置变量。
- 缺失 `TENCENT_COS_MEDIA_ENDPOINT` 时启动失败。
- 缺失 `TENCENT_COS_BACKUP_ENDPOINT` 时备份存储后端初始化失败。
- 缺失 `system_configs.media_public_base_url` 时媒体相关 API 返回 5xx，且对外文案与 error_code 规范一致。
- 缺失 `system_configs.media_public_base_url` 时应用启动不被阻断。
- 媒体上传链路写入的 `bucket_name` 与 `storage_region` 来自 `TENCENT_COS_MEDIA_*`。
- deployment 脚本、README、compose 文件中的服务命名完全一致。
- staging PostgreSQL 镜像已统一为 `postgres:18`。
- deployment 脚本不再校验旧单桶对象存储变量。
- 文档中不再出现旧单桶配置命名。

## 交付结果

- 媒体与备份配置分域完成。
- 媒体公开 URL 回退逻辑移除。
- 备份实施所需配置基线完成。
