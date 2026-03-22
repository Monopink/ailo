# 媒体：聊天图片（file_type=3）

## 目标

- 支持聊天图片上传与在聊天时间线中展示（`media_files.file_type=3`）。

## 现状（预留点）

- `media_files.file_type` 与 `FileType.IMAGE=3` 已存在，但上传规则未启用：
  - `backend/app/services/media/rules.py` 仅启用 `FileType.AVATAR`。
  - `backend/app/services/media/uploader.py` 对未启用类型直接返回 `400`（“当前仅支持头像上传”）。

## 待实现

- 启用 `FileType.IMAGE` 的上传规则（size、mime、quota、public/private）。
- 定义“消息如何引用图片”的稳定数据结构：
  - 需要明确 message.content / metadata 中的引用方式（例如 file_id、width/height、thumb）。
- 补齐客户端渲染规则（缩略图、点击预览、失败占位等）。

## 相关文档与代码

- Media API：`../../api/media.md`
- media_files 数据结构：`../../data-dict/storage.md#media_files`
- 消息数据结构：`../../spec/message/schema.md`
- 上传规则：`../../../backend/app/services/media/rules.py`
