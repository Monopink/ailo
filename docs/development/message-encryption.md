## Message Encryption – MVP Plan

### 背景

- 客户端与服务端需要支持统一的“消息加密”机制，短期内以 **Base64 编码** 作为占位，实现接口与 metadata 约束；后期再切换到 **AES-256-GCM** 或其他算法。
- 目标：让消息在“LeanCloud 传输层”保持加密格式，同时 **AI/业务逻辑仍使用明文**，并把算法信息写入事件/数据库，便于客户端解码与将来的密钥轮换。

### 架构

```
客户端 → LeanCloud → Webhook
    ↑                 ↓
  Base64 encode   decrypt_from_transport()
```

1. **Outbound（服务端→客户端）**
   - `services/message/sender.py` 在 `_send_message_internal` 中调用 `encrypt_for_transport()`。
   - 返回的 `encrypted_content` 写入 LeanCloud payload，`metadata.encryption/encryption_version` 合并到消息 JSON。
   - `EventMetadata`/`message_history.message_metadata` 也记录加密参数，便于审计。

2. **Inbound（客户端→服务端）**
   - `services/message/providers/leancloud/webhook.py` 在解析 `inner_message` 时读取 `encryption/enc_version`，调用 `decrypt_from_transport()`，得到明文后再进入 buffer/AI。
   - 若客户端仍发送明文，则缺少 `encryption` 字段，服务端将内容直接透传。

3. **持久化**
   - `message_events_schema.md` 的 `metadata` 新增 `encryption / encryption_version` 字段，并映射到 `message_history.message_metadata`。
   - 未来切换 AES 只需更新 `services/message/encryption.py` 的默认算法/密钥来源，无需修改业务层。

### 模块说明

文件：`backend/app/services/message/encryption.py`

| 函数 | 作用 |
|------|------|
| `encrypt()` / `decrypt()` | 算法无关的基础接口，支持 `EncryptionType.BASE64`、`EncryptionType.AES_256_GCM` |
| `_encode_base64` / `_decode_base64` | MVP 占位实现，**不需要 key** |
| `_encrypt_aes_256_gcm` / `_decrypt_aes_256_gcm` | 预留真实加密方案（key 必须 32 bytes） |
| `encrypt_for_transport()` | 使用默认算法（当前 Base64）封装传输逻辑 |
| `decrypt_from_transport()` | 根据 metadata 自动解密；metadata 缺失时返回原文 |

### 配置与后续计划

- 目前 `DEFAULT_ENCRYPTION = base64`，`DEFAULT_VERSION = v1`，不依赖任何 key。
- 未来切换 AES：
  - 在配置中心（如 system_configs）保存 key/版本；
  - 在 `encrypt_for_transport()` / `decrypt_from_transport()` 中读取 key；
  - metadata 中新增 `key_id`、`iv` 等字段（事件 schema 已支持额外字段）。

### 注意事项

- `cryptography` 已加入 `backend/app/requirements.txt`（版本 `46.0.3`），确保容器/打包阶段安装。
- 解密失败会记录 `leancloud_decrypt_failed` 日志，并回退到原文，避免消息丢失。
- 任何新增算法必须在 `EncryptionType`、`EncryptionVersion` 枚举与 schema 文档中登记。
