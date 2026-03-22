# 消息传输加密（AES-256-GCM）（未来）

目标：在不改变业务协议语义的前提下，为消息传输层引入可切换的加密能力。

## AES-256-GCM 预留方案

### 依赖

已加入 `backend/app/requirements-runtime.txt`：

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
  "enc_version": "v1"
}
```

### 未来字段（AES-256-GCM）

```json
{
  "encryption": "aes_256_gcm",
  "enc_version": "v2",
  "key_id": "key_20241201",
  "iv": "base64_encoded_iv"
}
```

## 错误处理

### 解密失败

**处理逻辑**：

1. 捕获解密异常
2. 记录错误日志（包含前 50 字符和 metadata）
3. 拒绝处理该消息并返回错误
