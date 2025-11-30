# 消息加密机制

本文档说明消息传输加密的完整方案。

- 短期使用 Base64 编码占位，实现接口与 metadata 约束
- 后期切换到 AES-256-GCM 或其他算法
- 客户端与服务端支持统一的加密机制
- 解密失败时回退到原文，避免消息丢失

## 架构设计

```
客户端 → LeanCloud → Webhook
    ↑                 ↓
  Base64 encode   decrypt_from_transport()
```

### Outbound（服务端 → 客户端）

**流程**：

1. 调用 encrypt_for_transport() 加密内容
2. 返回 encrypted_content 和 metadata
3. 将 encrypted_content 写入 LeanCloud payload
4. 将 metadata.encryption/encryption_version 合并到消息 JSON

### Inbound（客户端 → 服务端）

**流程**：

1. Webhook 解析 inner_message 时读取 encryption/enc_version
2. 调用 decrypt_from_transport() 解密
3. 若客户端发送明文（缺少 encryption 字段），服务端直接透传

### 持久化

metadata 新增字段，映射到 message_history.message_metadata：

```json
{
  "encryption": "base64",
  "encryption_version": "v1"
}
```

## 模块说明

**文件位置**：`backend/app/services/message/encryption.py`

### 核心函数

- `encrypt()` / `decrypt()` - 算法无关的基础接口，支持 BASE64、AES_256_GCM
- `_encode_base64()` / `_decode_base64()` - MVP 占位实现，不需要 key
- `_encrypt_aes_256_gcm()` / `_decrypt_aes_256_gcm()` - 预留真实加密方案（key 必须 32 bytes）
- `encrypt_for_transport()` - 使用默认算法（当前 Base64）封装传输逻辑
- `decrypt_from_transport()` - 根据 metadata 自动解密；metadata 缺失时返回原文

### 加密类型枚举

- BASE64 - Base64 编码（MVP 占位）
- AES_256_GCM - AES-256-GCM 加密（预留）

### 加密版本枚举

- V1 - 版本 1

## Base64 占位实现

### 当前配置

- DEFAULT_ENCRYPTION = BASE64
- DEFAULT_VERSION = V1

### 加密逻辑

**输入**：

- content（明文内容）

**输出**：

- encrypted_content（Base64 编码后的内容）
- metadata（包含 encryption 和 encryption_version）

**步骤**：

1. 使用 Base64 编码 content
2. 构建 metadata 对象
3. 返回 (encrypted_content, metadata)

### 解密逻辑

**输入**：

- encrypted_content（加密内容）
- metadata（加密元数据）

**输出**：

- 明文内容

**步骤**：

1. 检查 metadata 中的 encryption 字段
2. 如果缺失 → 返回原文（明文消息）
3. 如果存在 → 根据 encryption_type 选择解密算法
4. 解密失败 → 记录日志，回退到原文

## AES-256-GCM 预留方案

### 依赖

已加入 `backend/app/requirements.txt`：

```
cryptography==46.0.3
```

### 加密算法

**AES-256-GCM 加密**：

**输入**：

- content（明文内容）
- key（32 bytes 密钥）

**输出**：

- base64(iv + ciphertext + tag)

**步骤**：

1. 验证 key 长度为 32 bytes
2. 生成 12 bytes 随机 IV（96-bit nonce）
3. 使用 AESGCM 加密 content
4. 拼接 iv + ciphertext + tag
5. Base64 编码返回

**AES-256-GCM 解密**：

**输入**：

- encrypted（加密内容）
- key（32 bytes 密钥）

**输出**：

- 明文内容

**步骤**：

1. 验证 key 长度为 32 bytes
2. Base64 解码 encrypted
3. 提取 iv（前 12 bytes）
4. 提取 ciphertext（剩余部分）
5. 使用 AESGCM 解密
6. 返回明文

## 切换到 AES 的步骤

### 1. 配置管理

在 system_configs 表中添加：

- message_encryption_type - 加密算法（base64/aes_256_gcm）
- message_encryption_version - 加密版本（v1/v2）
- message_encryption_key - 加密密钥（32 bytes，base64 编码）
- message_encryption_key_id - 密钥 ID（用于密钥轮换）

### 2. 更新 encrypt_for_transport

**逻辑**：

1. 从 system_configs 读取 encryption_type 和 version
2. 如果 encryption_type == "aes_256_gcm"：
   - 读取 key 和 key_id
   - 使用 AES-256-GCM 加密
   - 构建 metadata（包含 key_id）
3. 否则：
   - 使用 Base64 编码
   - 构建 metadata
4. 返回 (encrypted_content, metadata)

### 3. 更新 decrypt_from_transport

**逻辑**：

1. 检查 metadata 中的 encryption 字段
2. 如果缺失 → 返回原文
3. 如果 encryption == "aes_256_gcm"：
   - 从 metadata 读取 key_id
   - 从 system_configs 读取对应的 key
   - 使用 AES-256-GCM 解密
4. 否则：
   - 使用 Base64 解码
5. 返回明文

### 4. 密钥轮换

**支持多个密钥同时存在**：

- 新消息使用当前 key_id 加密
- 旧消息根据 metadata 中的 key_id 选择对应密钥解密
- 配置项命名：`message_encryption_key_{key_id}`

## metadata 扩展字段

### 当前字段（Base64）

```json
{
  "encryption": "base64",
  "encryption_version": "v1"
}
```

### 未来字段（AES-256-GCM）

```json
{
  "encryption": "aes_256_gcm",
  "encryption_version": "v2",
  "key_id": "key_20241201",
  "iv": "base64_encoded_iv"
}
```

## 错误处理

### 解密失败

**处理逻辑**：

1. 捕获解密异常
2. 记录错误日志（包含前 50 字符和 metadata）
3. 回退到原文，避免消息丢失
4. 返回原文

### 监控告警

解密失败时触发告警：

- 记录到日志系统
- 发送到监控平台
- 通知管理员

## 安全建议

### 密钥管理

- ✅ 密钥存储在 system_configs 表，不写入代码
- ✅ 使用环境变量或密钥管理服务（如 AWS KMS）
- ✅ 定期轮换密钥
- ✅ 密钥长度必须符合算法要求（AES-256 需要 32 bytes）

### 传输安全

- ✅ HTTPS 传输
- ✅ LeanCloud Webhook 签名验证
- ✅ 时间戳验证防止重放

### 存储安全

- message_history.content 存储明文（数据库层加密）
- message_history.message_metadata 存储加密元数据
- 敏感字段使用数据库透明加密（TDE）

## 性能考虑

### Base64 性能

- 编码/解码速度快
- 无需密钥管理
- 适合 MVP 阶段

### AES-256-GCM 性能

- 加密/解密速度较快（硬件加速）
- 需要密钥管理开销
- 适合生产环境

### 优化建议

- 批量消息可以并行加密/解密
- 使用连接池减少密钥查询
- 缓存当前密钥（定期刷新）
