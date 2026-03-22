# 媒体：表情/贴纸（file_type=2）

## 目标

- 支持用户侧“表情/贴纸”资产上传与投递（`media_files.file_type=2`）。
- 客户端渲染不引入专用协议，统一使用 CDN URL。

## 现状（预留点）

- `media_files.file_type` 与 `FileType.EMOJI=2` 已存在，但上传规则未启用：
  - `backend/app/services/media/rules.py` 仅启用 `FileType.AVATAR`。
  - `backend/app/services/media/uploader.py` 对未启用类型直接返回 `400`（“当前仅支持头像上传”）。

## 协议与存储约束

- 消息侧表达：
  - 消息内容使用文本占位符（例如 `[emoji_key]`），客户端根据 key 映射到资源 URL 后渲染为图片。
- 分发：
  - 统一通过 `GET /api/v1/media/{file_id}` 获取 URL（public 或 presigned）。
  - 表情资源默认 public（除非后续明确需要私有化）。

## 待实现

- 启用 `FileType.EMOJI` 的上传规则（size、mime、quota、public/private）。
- 定义 emoji 包清单、版本与缓存策略（客户端需要稳定的 key→URL 映射来源）。

## 相关文档与代码

- Media API：`../../api/media.md`
- media_files 数据结构：`../../data-dict/storage.md#media_files`
- 上传规则：`../../../backend/app/services/media/rules.py`
