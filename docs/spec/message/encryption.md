# 消息加密机制

本文档描述消息传输层加密处理的当前行为。

## 当前行为

### Outbound（服务端 → 客户端）

- `encrypt_for_transport(content)` 返回原文 `content`，并返回空对象 `{}` 作为 metadata。

### Inbound（客户端 → 服务端）

- `decrypt_from_transport(encrypted_content, metadata)`：
  - 当 `metadata` 为空或不包含 `encryption` 时，直接返回 `encrypted_content`（视为明文）。
  - 当 `metadata.encryption` 存在时，按 `metadata` 解密；不支持的 `encryption` 值会导致解密失败并抛出异常，由调用方决定如何处理无效 payload。

## metadata 字段（当存在时）

- `encryption`：加密算法（当前仅支持 `base64`）
- `enc_version`：加密版本（例如 `v1`）

说明：

- Provider 入站载荷使用 `enc_version`；服务端内部事件结构使用 `encryption_version`（见 `schema.md`），适配层负责映射。

## 相关实现

- `backend/app/services/message/security/encryption.py`
