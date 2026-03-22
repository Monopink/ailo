# 媒体上传：Magic Bytes 验证

## 目标

- 验证上传文件的实际类型与声明的 `mime_type` 一致，降低伪装文件带来的风险（例如 exe→jpg、html→img）。

## 现状

- 上传链路只基于 `mime_type` 与配置白名单进行校验，缺少对文件内容的签名检测。

## 待实现

- 在上传链路中增加 magic-bytes 检测：
  - 对图片类格式（jpg/png/webp）做最小签名校验。
  - 当检测结果与 `mime_type` 不一致时拒绝上传并返回稳定错误语义。
- 将签名检测与现有规则（size、quota、allowed_mimes）组合为单一的“上传校验器”入口，避免多处重复。

## 相关文档与代码

- Media API：`../../api/media.md`
- 上传入口：`../../../backend/app/api/v1/media.py`
- 上传流程：`../../../backend/app/services/media/uploader.py`
