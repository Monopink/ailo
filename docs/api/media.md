# 媒体文件接口

管理用户上传的媒体文件（头像、表情、图片等）。

---

## 接口列表

### POST /api/v1/media/upload

统一的后台代理上传接口。客户端通过 `multipart/form-data` 将文件上传到业务服务，由后端完成配额校验、格式校验、去重、推送对象存储以及 URL 生成。微信小程序与用户侧资料流程使用该接口。

**认证**: 必需（Bearer Token）

说明：本接口使用用户 JWT 鉴权，不用于管理端 session 鉴权场景。管理端 profile 头像高级编辑使用 `POST /admin-api/profile/{profile_id}/avatar/upload`。

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

**错误响应**:

不支持的文件类型 (400):
```json
{
  "error_code": 23010001,
  "message": "当前仅支持头像上传",
  "request_id": "req_20260215_a1"
}
```

文件大小不匹配 (400):
```json
{
  "error_code": 23010001,
  "message": "文件大小不匹配，请重新选择图片",
  "request_id": "req_20260215_a2"
}
```

文件过大 (413):
```json
{
  "error_code": 23010007,
  "message": "文件大小超过限制，头像最大 2MB",
  "request_id": "req_20260215_a3"
}
```

MIME 类型不支持 (415):
```json
{
  "error_code": 23010007,
  "message": "不支持的文件类型，仅支持 JPEG/PNG/WebP",
  "request_id": "req_20260215_a4"
}
```

超过配额或频率限制 (429):
```json
{
  "error_code": 23010006,
  "message": "今日上传次数已达上限",
  "request_id": "req_20260215_a5"
}
```

**配额与速率限制**:

- 配额与速率限制的阈值由服务端配置管理，客户端不得写死。
- 超限时返回 `429`，并包含 `Retry-After`。

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

**错误响应**:

无权操作 (403):
```json
{
  "error_code": 23010003,
  "message": "无权操作",
  "request_id": "req_20260215_b1"
}
```

文件不存在 (404):
```json
{
  "error_code": 23010004,
  "message": "文件不存在",
  "request_id": "req_20260215_b2"
}
```

---

### POST /admin-api/profile/{profile_id}/avatar/upload

管理端 Profile 头像高级编辑上传接口。接口完成文件接收、裁切参数处理、头像标准化处理（转码/缩放）并绑定到目标 profile。

**认证**: 必需（Admin Session）

**精度约束**: `profile_id` / `avatar_media_id` 为 Snowflake BIGINT。为避免前端 JS Number 精度丢失，本接口响应字段统一使用 **字符串**。

**请求方式**: `multipart/form-data`

**路径参数**:
- `profile_id` (必填): 目标 profile ID

**表单字段**:
- `file` (必填): 原始图片文件。
- `file_type` (必填): 固定为 `1`（avatar）。
- `mime_type` (必填): 客户端文件 MIME 类型。
- `file_size` (必填): 文件大小（字节）。
- `original_name` (可选): 原始文件名。
- `crop_x` (可选): 裁切区域左上角 X（像素）。
- `crop_y` (可选): 裁切区域左上角 Y（像素）。
- `crop_size` (可选): 裁切区域边长（像素，1:1）。

**请求语义**:
- 上传成功后立即覆盖目标 profile 当前头像
- 同步写入 `user_profile_logs`，`field_name=avatar_media_id`，`modified_by_type=2(admin)`
- 头像处理产物统一为 `WebP 512x512`
- 不保留原图
- 不执行每日上传配额校验
- 执行上传速率限制

**错误响应**:
- 管理端统一错误结构见 `docs/api/error-codes.md` 中 `/admin-api/*` 规范

---

### POST /admin-api/profile/{profile_id}/avatar/clear

管理端 Profile 头像清空接口。接口清空目标 profile 的头像字段并返回默认头像 URL。

**认证**: 必需（Admin Session）

**请求方式**: `POST`

**路径参数**:
- `profile_id` (必填): 目标 profile ID

**成功响应 (200)**:
```json
{
  "profile_id": "10001",
  "avatar_media_id": null,
  "avatar_url": "https://cdn.example.com/avatars/default.webp"
}
```

**请求语义**:
- 清空 `profiles.avatar_key` 与 `profiles.avatar_media_id`
- 写入 `user_profile_logs`，`field_name=avatar_media_id`，`change_reason=admin_avatar_clear`
- 返回清空后的头像 URL（默认头像）

**错误响应**:
- 管理端统一错误结构见 `docs/api/error-codes.md` 中 `/admin-api/*` 规范

---

### GET /admin-api/profile/owner-link/{owner_kind}/{owner_id}

管理端 owner 到 profile detail 的跳转解析接口。用于用户/AI Persona/AI Instance 列表快速进入对应资料详情页。

**认证**: 必需（Admin Session）

**路径参数**:
- `owner_kind` (必填): `user` | `ai_persona` | `ai_instance`
- `owner_id` (必填): owner 的内部 ID

**行为**:
- 解析 owner 对应 profile：
  - `user`：按 `(owner_type=1, owner_id=<owner_id>)`
  - `ai_persona`：按 `(owner_type=2, owner_id=<owner_id>)`
  - `ai_instance`：先取实例 `qiao_id`，再按 `owner_qiao_id=<instance.qiao_id>` 且 `owner_type in (2,3)` 查 profile
- 解析成功后返回 `303` 重定向到：`/qiao-dash/profile/detail/{profile_id}`

**错误响应**:
- `400`：`owner_kind` 非法
- `404`：owner 或 profile 不存在

---

## 错误码汇总

| HTTP 状态码 | error_code | message | 说明 |
|-----------|------------|---------|------|
| 200 | - | - | 成功 |
| 400 | 23010001 | 当前仅支持头像上传 | file_type 不是 1 |
| 400 | 23010001 | 文件大小不匹配 | 提交的 file_size 与实际不一致 |
| 413 | 23010007 | 文件大小超过限制 | 超过单文件大小限制 |
| 415 | 23010007 | 不支持的文件类型 | MIME 类型不在白名单 |
| 429 | 23010006 | 今日上传次数已达上限 | 超过每日上传次数配额 |
| 429 | 23010006 | 请求过于频繁 | 超过速率限制 |
| 403 | 23010003 | 无权操作 | 文件不属于当前用户 |
| 404 | 23010004 | 文件不存在 | 指定 file_id 不存在或已被删除 |

---

## 参考资料

- [对象存储规范](../spec/storage.md) - 上传流程、去重策略、安全措施
- [头像上传规范](../spec/client/mini-program/avatar-upload.md) - 小程序头像上传对接指南
- [用户资料 API](user.md) - 头像应用接口
- [管理端总览](../spec/admin-panel/overview.md) - 管理端能力入口
- [系统配置 API](system.md) - 配额配置
