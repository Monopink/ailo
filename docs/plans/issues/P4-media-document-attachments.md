# 媒体：文件附件（file_type=4）

## 目标

- 支持文件附件上传与消息引用（`media_files.file_type=4`）。
- 默认私有访问（对外只暴露短时 URL，不暴露永久可猜测地址）。

## 现状（预留点）

- `media_files.file_type` 与 `FileType.DOCUMENT=4` 已存在，但上传规则未启用：
  - `backend/app/services/media/rules.py` 仅启用 `FileType.AVATAR`。
  - `backend/app/services/media/uploader.py` 对未启用类型直接返回 `400`（“当前仅支持头像上传”）。
- 私有 URL 能力已具备：
  - `/api/v1/media/{file_id}` 会在 `is_public=false` 时返回 presigned URL（GET）。

## 待实现

- 启用 `FileType.DOCUMENT` 的上传规则（size、mime、quota、public/private）。
- 定义附件在消息中的引用结构（file_id、文件名、大小、mime）。
- 定义下载体验与权限边界（仅上传者可访问、或按会话参与方授权）。

## 相关文档与代码

- Media API：`../../api/media.md`
- media_files 数据结构：`../../data-dict/storage.md#media_files`
- 消息数据结构：`../../spec/message/schema.md`
- URL 生成：`../../../backend/app/services/media/url.py`
- 上传规则：`../../../backend/app/services/media/rules.py`
