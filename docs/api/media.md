# 媒体文件接口

管理用户上传的媒体文件（头像、表情、图片等）。

---

## 接口列表

### POST /api/v1/media/upload

统一的后台代理上传接口。客户端通过 `multipart/form-data` 将文件上传到业务服务，由后端完成配额校验、格式校验、去重、推送对象存储以及 URL 生成。微信小程序与管理后台必须使用该接口。

**认证**: 必需（Bearer Token）

**请求方式**: `multipart/form-data`

**表单字段**:
- `file` (必填): 经过裁剪压缩的头像文件 (WebP)。
- `file_type` (必填): 文件类型，当前仅支持 `1` (avatar)。
- `mime_type` (必填): MIME 类型，例如 `image/webp`。
- `file_size` (必填): 文件大小（字节），用于配额与快速校验。
- `original_name` (可选): 原始文件名，便于审计。
- `file_hash` (可选): 文件 SHA-256（小写 hex），用于加速去重（未提供时后端自动计算）。

**示例**:
```bash
curl -X POST "https://api.example.com/api/v1/media/upload" \
  -H "Authorization: Bearer <TOKEN>" \
  -F "file=@avatar.webp" \
  -F "file_type=1" \
  -F "mime_type=image/webp" \
  -F "file_size=185423" \
  -F "original_name=avatar.webp"
```

**成功响应 (200)**:
```json
{
  "file_id": "file_1285612345678901234",
  "url": "https://cdn.example.com/avatars/2025/12/1285612345678901234.jpg",
  "duplicate": false
}
```

**响应字段**:
- `file_id`: 文件唯一标识符。
- `url`: 激活后即可访问的 CDN URL。
- `duplicate`: 是否命中去重（命中时 `url` 会指向旧文件）。

**后端处理要点**:
1. 验证用户身份、文件类型以及每日上传配额。
2. 执行速率限制（默认 10 次/分钟）。
3. 校验 `mime_type`、`file_size`，必要时拒绝请求。
4. 基于 `file_hash`（客户端提供或后端自动计算）执行去重。
5. 将文件写入对象存储（Local/COS），并立即创建 `media_files` 记录（status=ACTIVE）。
6. 返回 `{file_id, url, duplicate}`，供前端直接展示或写入资料。

**错误响应**:

不支持的文件类型 (400):
```json
{
  "detail": "当前仅支持头像上传"
}
```

文件大小不匹配 (400):
```json
{
  "detail": "文件大小不匹配，请重新选择图片"
}
```

文件过大 (413):
```json
{
  "detail": "文件大小超过限制，头像最大 2MB"
}
```

MIME 类型不支持 (415):
```json
{
  "detail": "不支持的文件类型，仅支持 JPEG/PNG/WebP"
}
```

超过配额或频率限制 (429):
```json
{
  "detail": "今日上传次数已达上限（5 次/天）"
}
```

**配额限制** (MVP):
| 文件类型 | 单文件大小 | 每日上传次数 | 每日总大小 |
|---------|-----------|-------------|-----------|
| 头像 (avatar) | 2MB | 5 次 | 10MB |

> 说明：整个上传/确认流程全部由后端托管，客户端仅需调用此接口即可完成头像上传与激活。

---

### GET /api/v1/media/{file_id}

获取文件访问 URL（用于头像等资源的动态加载）。

**认证**: 必需

**路径参数**:
- `file_id`: 文件 ID（格式：file_xxx）

**成功响应 (200)**:
```json
{
  "file_id": "file_1285612345678901234",
  "url": "https://cdn.example.com/avatars/2025/12/1285612345678901234.jpg",
  "mime_type": "image/jpeg",
  "file_size": 102400,
  "created_at": "2025-12-20T08:20:00+00:00"
}
```

**响应字段**:
- `file_id`: 文件 ID
- `url`: 公开访问 URL（CDN 或 COS 直链）
- `mime_type`: MIME 类型
- `file_size`: 文件大小（字节）
- `created_at`: 激活时间

**后端处理要点** (P0):
1. 验证文件所有权 (`upload_by_id == current_user.id`)
2. 验证文件已激活 (`status == ACTIVE`)
3. 生成公开 URL（公共文件直接返回 CDN，私有文件返回代理地址）

**错误响应**:

无权操作 (403):
```json
{
  "detail": "无权操作"
}
```

文件不存在 (404):
```json
{
  "detail": "文件不存在"
}
```

---

## 错误码汇总

| HTTP 状态码 | detail | 说明 |
|-----------|--------|------|
| 200 | - | 成功 |
| 400 | 当前仅支持头像上传 | file_type 不是 1 |
| 400 | 文件大小不匹配 | 提交的 file_size 与实际不一致 |
| 413 | 文件大小超过限制 | 超过单文件大小限制 |
| 415 | 不支持的文件类型 | MIME 类型不在白名单 |
| 429 | 今日上传次数已达上限 | 超过每日上传次数配额 |
| 429 | 请求过于频繁 | 超过速率限制（10/分钟） |
| 403 | 无权操作 | 文件不属于当前用户 |
| 404 | 文件不存在 | 指定 file_id 不存在或已被删除 |

---

## 参考资料

- [对象存储规范](../spec/storage.md) - 上传流程、去重策略、安全措施
- [前端实施规范](../spec/avatar-upload-frontend.md) - 小程序/管理后台对接指南
- [用户资料 API](user.md) - 头像应用接口
- [系统配置 API](system.md) - 配额配置
