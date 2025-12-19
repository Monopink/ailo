# 对象存储规范

## 概述

本文档定义媒体管理系统的对象存储架构、数据流和实现标准。

---

## 架构设计

### 存储抽象层

```
应用层 (FastAPI)
    ↓
存储服务 (backend/app/services/storage/)
    ↓
fsspec 抽象层
    ↓
存储后端:
├── LocalStorageBackend (开发/测试)
└── TencentCOSBackend (生产环境)
```

### 核心原则

1. **提供商无关**: 应用代码不直接依赖特定存储提供商
2. **配置驱动**: 通过配置选择存储提供商，无需修改代码
3. **动态生成 URL**: 永不存储完整 URL，始终动态生成
4. **安全优先**: 私有内容使用预签名 URL，公开内容使用 CDN
5. **成本优化**: 启用 CDN 加速，实施去重策略

---

## 存储后端

### 本地存储 (开发环境)

**用途**: 开发、测试、CI/CD

**配置**:
```bash
STORAGE_PROVIDER=local
STORAGE_LOCAL_PATH=/app/media
STORAGE_LOCAL_URL=http://localhost:8000/media
```

**特点**:
- 文件存储在容器文件系统
- 无成本，配置简单
- 不适用于生产（无冗余、扩展性有限）

### 腾讯云 COS (生产环境)

**用途**: 生产部署

**配置**:
```bash
STORAGE_PROVIDER=tencent_cos
TENCENT_COS_SECRET_ID=your-secret-id
TENCENT_COS_SECRET_KEY=your-secret-key
TENCENT_COS_REGION=ap-beijing
TENCENT_COS_BUCKET=media-prod
TENCENT_COS_CDN_DOMAIN=https://cdn.example.com
```

---

## 对象键命名规范

### 格式

```
{文件类型}/{年份}/{月份}/{snowflake_id}.{扩展名}

示例:
avatars/2025/12/1285612345678901234.jpg
emojis/2025/12/1285612345678901235.png
images/2025/12/1285612345678901236.webp
```

---

## URL 生成策略

### 公开 URL (可缓存内容)

**用途**:
- 系统默认头像（COS avatar/default.webp，永不变更，由 `TENCENT_COS_CDN_DOMAIN` 或 `TENCENT_COS_ENDPOINT` 动态拼接）
- 用户头像（确认上传后）

**特点**:
- 永久有效
- 可缓存（30 天）
- CDN 加速
- 无需认证

**生成规则**:
```
{cdn_domain}/{object_key}
或
{bucket_url}/{object_key}
```

### 预签名 URL (私有内容)

**用途**:
- 上传操作（写入）
- 私有文档（读取）
- 临时访问授权

**特点**:
- 时间限制（上传 5 分钟，下载 1 小时）
- 不走 CDN（绕过缓存）
- 包含认证签名
- 自动过期

**安全要求**:
- **Content-Type 绑定**: 预签名 URL 必须限制上传的 Content-Type
- **Content-Length 绑定**: 预签名 URL 必须限制上传的文件大小
- **HTTP 方法绑定**: 上传 URL 仅允许 PUT

---

## 上传流程

### 后端代理上传

```
1. 客户端选择/裁剪图片并获取 file_size、(可选) file_hash
2. 客户端通过业务域名调用 POST /api/v1/media/upload (multipart/form-data)
3. 后端验证身份、配额、速率限制
4. 后端校验 file_type/file_size/mime_type 是否合规
5. 后端根据 file_hash（客户端提供或自动计算）执行去重
6. 后端写入对象存储并立即创建 media_files 记录（status=ACTIVE）
7. 后端返回 {file_id, url, duplicate}
8. 客户端如需绑定头像，调用 PUT /api/v1/user/profile
```

**安全检查要点** (P0):
- 上传时：验证配额、格式以及 `upload_by_id`（记录由后端写入）
- 应用头像时：验证 `upload_by_id == current_user.id` 且 `status == ACTIVE`
- 查询文件时：验证 `upload_by_id == current_user.id`

---

## 文件校验

### 上传前校验（/media/upload 阶段）

```python
VALIDATION_RULES = {
    'avatar': {
        'max_size': 2 * 1024 * 1024,
        'allowed_mimes': ['image/jpeg', 'image/png', 'image/webp'],
        'daily_quota': 5,
        'daily_size_quota': 10 * 1024 * 1024,
    }
}
```

- `file_type`：必须存在并有对应规则
- `file_size`：与配置的 `max_size` 比较，同时与客户端字段对比
- `mime_type`：需要在白名单
- 配额：`daily_quota`、`daily_size_quota`
- 速率限制：默认 10 次/分钟（可在 `rate_limiter` 配置）

### 写入后校验

- 本地/代理写入后即刻记录 `media_files`（status=ACTIVE）
- 若写入失败则直接返回 503，并不会生成记录
- 本地存储会记录 `.meta` 文件，包含 size/content_type/etag，便于排查
- 对于客户端提供的 `file_hash`，在写入前直接去重；若未提供，后端以文件内容计算 hash 并写入

**错误处理**:
- 413：单文件超限
- 415：MIME 不在白名单
- 400：客户端声明的 file_size 与实际长度不符
- 503：对象存储写入失败

---

## 文件去重

### 策略

**客户端计算 SHA-256** (优先) → **js-sha256 库** (降级) → **后端同步计算** (最终)

### 客户端实现

```javascript
// 1. 优先使用原生 Web Crypto API (15-40ms)
const hashBuffer = await crypto.subtle.digest('SHA-256', arrayBuffer);

// 2. 降级使用 js-sha256 库 (60-120ms)
const sha256 = require('js-sha256');
const hash = sha256(arrayBuffer);

// 3. 失败则返回 null，后端处理
return null;
```

### 后端处理

**Token 阶段**: 如果客户端提供 hash，立即检查去重

**Confirm 阶段**: 如果客户端未提供 hash：
1. 同步下载文件（~300ms for 2MB）
2. 计算 SHA-256（~50ms）
3. 检查去重
4. 如果重复，删除新文件，返回旧文件 URL
5. 如果不重复，更新 hash 字段

**性能影响**:
- 增加延迟：~350ms（可接受）
- 去重率：30-50%
- 节省成本：~¥36/年（10K 用户）

**去重规则**:
- 仅在同一用户范围内去重（`upload_by_id == current_user.id`）
- Token 阶段：如果提供 hash 且已存在，直接返回 URL
- Confirm 阶段：如果未提供 hash，后端下载并计算 hash 再去重

---

## 孤儿文件清理

### 定时任务

**执行频率**: 每小时

**清理条件**:
```sql
SELECT id, object_key
FROM media_files
WHERE status = 2  -- pending
  AND created_at < NOW() - INTERVAL '1 hour'
```

**清理动作**:
1. 删除 COS 对象
2. 软删除数据库记录（`status=3`）

### 扩展清理

**每日执行**, 清理已激活但未被引用的文件:
```sql
SELECT mf.id, mf.object_key
FROM media_files mf
LEFT JOIN profiles p ON p.avatar_file_id = mf.id
WHERE mf.status = 1  -- active
  AND mf.file_type = 1  -- avatar
  AND mf.confirmed_at < NOW() - INTERVAL '24 hours'
  AND p.id IS NULL  -- 未被任何 profile 引用
```

**安全理由**:
- 防止黑产刷存储
- 防止"申请 token 不确认"攻击
- 防止被当作永久图床

---

## CDN 配置

### 缓存规则

| 内容类型 | 缓存时长 | 缓存键 |
|---------|---------|--------|
| 系统默认头像 | 365 天 | object_key |
| 用户头像 | 30 天 | object_key |
| 用户图片 | 7 天 | object_key |
| 私有文档 | 不缓存 | 使用预签名 URL |

### CORS 配置

```json
{
  "CORSRules": [{
    "AllowedOrigin": ["https://servicewechat.com"],
    "AllowedMethod": ["GET", "PUT", "POST", "HEAD"],
    "AllowedHeader": ["*"],
    "ExposeHeader": ["ETag"],
    "MaxAgeSeconds": 3600
  }]
}
```

---

## 安全措施

- 文件所有权验证（所有文件操作）
- 预签名 URL 绑定 Content-Type/Content-Length
- 上传确认完整性校验（大小、类型、ETag）
- 每日上传配额限制（头像 5 次/天，图片 20 次/天）
- 孤儿文件定时清理（每小时）
- 速率限制（10 次/分钟）

### 文件所有权验证

**强制规则**:
- 所有文件操作必须验证 `media_files.upload_by_id == current_user.id`
- 适用接口：POST /api/v1/media/upload、GET /api/v1/media/{file_id}、PUT /api/v1/user/profile

**实现要点**:
- 文件不存在或已删除 → 404
- 文件不属于当前用户 → 403
- 状态为 pending 且操作非 confirm → 404

### 预签名 URL 约束

**生成要求**:
- 绑定 Content-Type（防止MIME类型篡改）
- 绑定 Content-Length（防止大小篡改）
- HTTP 方法绑定（上传仅允许 PUT）
- 5 分钟有效期

**客户端上传要求**:
- 必须携带 `Content-Type` header，与申请 token 时声明的一致
- 必须携带 `Content-Length` header，与申请 token 时声明的一致
- 否则 COS 返回 403 SignatureDoesNotMatch

### 孤儿文件清理实施

**清理策略**:
- 执行频率：每小时
- 清理条件：status=pending 且 created_at > 1 小时
- 清理动作：删除 COS 对象 + 软删除数据库记录

**实施方式**:
- 推荐：Celery Beat 定时任务
- 备选：Docker Compose + cron 容器、APScheduler

**监控要点**:
- 记录每次清理的文件数量
- 单次清理 > 100 个文件时告警（可能是攻击）

---

## 参考资料

- [fsspec 文档](https://filesystem-spec.readthedocs.io/)
- [腾讯云 COS 文档](https://cloud.tencent.com/document/product/436)
- [S3 API 兼容性指南](https://cloud.tencent.com/document/product/436/37421)
- [存储安全规范](storage-security.md)
- [资料数据字典](../data-dict/profile.md)
- [媒体 API 文档](../api/media.md)
