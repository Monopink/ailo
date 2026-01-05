# CDN URL 架构优化方案

## 任务背景

在实施头像上传功能时，发现原有的 CDN URL 配置存在过度设计问题，需要重新审视并优化架构。

## 问题分析

### 原设计问题

1. **配置来源不明确**
   - 原有：环境变量 `MEDIA_PUBLIC_BASE_URL` 硬编码到代码中
   - 问题：修改 CDN 域名需要重启服务（downtime）
   - 需求：支持运行时动态修改 CDN 配置

## 最终架构方案

### 核心原则

> **system_configs 为主，环境变量作为 fallback，必须支持运行时热更新**

### 配置层次

```
┌─────────────────────────────────────┐
│  system_configs.media_public_base_url │  <-- 权威配置，可由后台随时修改
│  (Admin / Starlette Admin)          │
└─────────────────────────────────────┘
          │
          ▼  (初始化时写入 Storage Backend 并缓存)
┌─────────────────────────────────────┐
│  Storage Backend (lru_cache)        │  <-- 应用启动时初始化
│  TencentCOSBackend(cdn_domain=...)  │
└─────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────┐
│  URL 生成                           │
│  {cdn_domain}/{object_key}          │
└─────────────────────────────────────┘

          ▲
          │ (仅当 system_configs 为空时回退)
┌─────────────────────────────────────┐
│  环境变量 MEDIA_PUBLIC_BASE_URL     │  <-- 部署期默认值 / 紧急 fallback
│  (.env 文件)                        │
└─────────────────────────────────────┘
```

### 实现细节

#### 1. system_configs 配置（主要方式）

**表结构**：`system_configs`

```sql
('media_public_base_url', 'https://cdn-dev.example.com', '', 1,
 'Authoritative public base URL for serving media files (CDN or COS bucket domain)',
 'media', NULL)
```

**规则**：
- `config_value` 必须填写可用的 CDN/COS 域名，系统读取不到值时视为严重配置错误
- 管理后台修改后需要触发 storage backend 的 cache clear（见下文）
- `default_value` 保持为空，用于提醒「必须由运维设置，而不是靠默认值」

#### 2. 环境变量配置（fallback）

**文件**：`deployment/.env.example`

```bash
# Public base URL fallback for serving uploaded media
# Backend will use this value only when system_configs.media_public_base_url is empty.
# Examples:
#   - COS bucket domain: https://bucket-name.cos.region.myqcloud.com
#   - CDN domain: https://cdn.example.com
MEDIA_PUBLIC_BASE_URL=
```

**用途**：
- 部署初期用于一次性写入 system_configs
- system_configs 为空时由 backend 自动读取并写入缓存，但会同时记录告警
- 紧急情况下可通过重启 + env 临时兜底，但仍需尽快恢复 system_configs

#### 3. Storage Factory 实现

**文件**：`backend/app/services/storage/factory.py`

```python
from app.services.media.config import get_media_base_url

@lru_cache
def get_storage_backend() -> StorageBackend:
    """Return cached storage backend instance."""
    settings = get_settings()
    cdn_domain = get_media_base_url()
    return TencentCOSBackend(
        secret_id=settings.TENCENT_COS_SECRET_ID,
        secret_key=settings.TENCENT_COS_SECRET_KEY,
        region=settings.TENCENT_COS_REGION,
        bucket=settings.TENCENT_COS_BUCKET,
        endpoint=settings.TENCENT_COS_ENDPOINT or None,
        cdn_domain=cdn_domain,
    )
```

**关键点**：
- 使用 `@lru_cache` 缓存单例
- 在应用启动时初始化
- 直接从环境变量读取 CDN 域名

## 技术决策

### 为什么以 system_configs 为主？

1. ✅ **运行时可控**：Starlette Admin/专用 API 能直接更新数据库，无需重启
2. ✅ **多实例一致性**：集中式配置避免「A 机 env 已更新、B 机未更新」的问题
3. ✅ **可审计**：system_configs 自带修改记录，方便排查配置漂移
4. ✅ **符合既有决策**：Dual-Track 配置原则要求业务参数放在数据库

### 环境变量的职责？

- 提供部署阶段的初始值或紧急 fallback
- 允许不同环境（dev/staging/prod）在第一次启动时有合理默认值
- 但一旦系统运行，应立即通过管理后台写入 system_configs，backend 也会在启动时记录日志，提醒 env fallback 处于启用状态

### 为什么保留 `category` 字段？

**为未来扩展预留**：
- `file_type` 提供主分类：1=avatar, 2=emoji, 3=image, 4=document
- `category` 提供次级分类（可选）：
  - Avatar: `user_avatar`, `system_preset`, `group_avatar`
  - Image: `sticker`, `photo`, `screenshot`
  - Document: `pdf`, `word`, `excel`
- 当前未使用，但数据库设计时预留，避免未来 schema 变更

## 实施清单

### ✅ 已完成

1. **添加 system_configs 配置项**：
   - ✅ `backend/database/init/02_required_data.sql` - `media_public_base_url`

2. **完善 MediaFileView 字段**：
   - ✅ 添加 `category` 字段
   - ✅ 添加 `storage_region` 字段
   - ✅ 添加 `confirmed_at` 字段
   - ✅ 添加 `confirmed_by_id` 字段

3. **创建数据字典**：
   - ✅ `docs/data-dict/media_files.md`

4. **system_configs 主配置**：
   - ✅ `backend/database/init/02_required_data.sql` 更新为权威值
   - ✅ 后端提供 `refresh_media_base_url()` + `get_media_base_url()` 并结合 storage factory 缓存

### ⏳ 待测试

1. **重启后端验证**：
   - 数据库初始化是否成功
   - MediaFileView 是否正常显示
   - URL 生成是否正确

2. **端到端测试**：
   - 头像上传功能
   - Profile 更新功能

## URL 生成示例

### 公开 URL（is_public=true）

```python
# 配置
MEDIA_PUBLIC_BASE_URL = "https://cdn.example.com"

# 存储
object_key = "avatars/2025/12/223788765171155003.jpg"

# 生成
url = f"{cdn_domain}/{object_key}"
# 结果: https://cdn.example.com/avatars/2025/12/223788765171155003.jpg
```

**特点**：
- 永久有效
- CDN 加速（30天缓存）
- 无需认证

### 私有 URL（is_public=false）

动态生成预签名 URL：
```python
# 上传 URL：5分钟有效，PUT only
upload_url = storage.generate_presigned_upload_url(
    object_key=object_key,
    content_type="image/jpeg",
    content_length=102400,
    expires_in=300
)

# 下载 URL：1小时有效，GET only
download_url = storage.generate_presigned_download_url(
    object_key=object_key,
    expires_in=3600
)
```

**特点**：
- 时间限制（自动过期）
- 不走 CDN（绕过缓存）
- 包含认证签名

## 未来扩展方向

### 如需支持运行时 CDN 切换

1. **实现 cache 清除机制**：
   ```python
   def reload_storage_backend():
       """Clear cache and reload storage backend."""
       get_storage_backend.cache_clear()
       # Force re-initialize
       return get_storage_backend()
   ```

2. **添加管理后台接口/操作按钮**：
   - 修改 `system_configs.media_public_base_url`
   - 调用 `reload_storage_backend()`，让所有实例重新读取新的 CDN 域名
   - 对结果进行审计记录

3. **考虑灰度发布**：
   - 支持多个 CDN 域名（轮询或权重）
   - A/B 测试不同 CDN 提供商

### 如需支持多区域部署

在 `system_configs` 中添加区域路由配置：
```sql
('media_cdn_region_mapping', '{"ap-guangzhou": "https://cdn-gz.example.com", "ap-shanghai": "https://cdn-sh.example.com"}', '', 4, 'CDN domain mapping by region', 'media', NULL)
```

## 相关文档

- [对象存储规范](../spec/storage.md) - 完整的存储架构设计
- [Media Files 数据字典](../data-dict/media_files.md) - 表结构详细说明
- [Media API 文档](../api/media.md) - 文件上传和管理接口

## 总结

这次架构优化遵循了以下原则：

1. **YAGNI 原则**：CDN 配置保持在系统级别，避免冗余字段
2. **KISS 原则**：系统只维护单一权威配置（system_configs），避免多入口冲突
3. **灵活性预留**：通过 `reload_storage_backend()` 支持运行时切换，结合 Admin/SQL 修改
4. **性能优先**：storage backend 仍由 LRU 缓存承载，URL 生成无需额外查询

**关键决策**：system_configs 为主、环境变量仅作 fallback，确保无停机切换并保持多实例一致性。
