# 账户安全管理接口

## 接口列表

- [发送验证码](#发送验证码) - `POST /api/v1/auth/user/verify/send-code`
- [确认验证码](#确认验证码) - `POST /api/v1/auth/user/verify/confirm`
- [修改手机号](#修改手机号) - `PUT /api/v1/user/phone`

---

## 统一验证机制

### 发送验证码

#### 基本信息

- **路径**: `POST /api/v1/auth/user/verify/send-code`
- **认证**: Bearer Token（必需）
- **速率限制**: 受限流保护

#### 请求参数

```json
{
  "verify_type": "phone",
  "target": "+8613800138000"
}
```

**字段说明**:

- `verify_type` (string, 必填)
  - 验证类型
  - 可选值: `phone`

- `target` (string, 可选)
  - 目标手机号
  - 默认为当前用户手机号
  - 用于修改手机号时，可以指定新的手机号作为 target

#### 成功响应 (200)

```json
{
  "cooldown": 60
}
```

**字段说明**:

- `cooldown` (integer) - 冷却时间（秒）

#### 错误响应

**400 Bad Request**:

- `"请先绑定手机号"`
- `"请30秒后再试"` - 触发限流保护

**500 Internal Server Error**:

- `"系统错误（error_code）"` - 服务器内部错误

---

### 确认验证码

#### 基本信息

- **路径**: `POST /api/v1/auth/user/verify/confirm`
- **认证**: Bearer Token（必需）

#### 请求参数

```json
{
  "verify_type": "phone",
  "code": "123456"
}
```

**字段说明**:

- `verify_type` (string, 必填)
  - 验证类型
  - 可选值: `phone`

- `code` (string, 必填)
- 验证码固定为 6 位

#### 成功响应 (200)

```json
{
  "operation_token": "opt_xxx",
  "expires_in": 300
}
```

**字段说明**:

- `operation_token` (string) - 操作令牌，用于敏感操作
- `expires_in` (integer) - 有效期（秒），默认5分钟

#### 错误响应

**400 Bad Request**:

- `"请先绑定手机号"`
- `"验证码有误，请重新输入"` - 验证码不正确
- `"验证码已失效，请重新获取"` - 验证码已失效

**500 Internal Server Error**:

- `"系统错误（error_code）"` - 服务器内部错误

#### 业务说明

- 验证成功返回 `operation_token`
- `operation_token` 有效期5分钟
- 用于敏感操作（修改手机号等）

---

## 修改手机号

### 修改手机号

#### 基本信息

- **路径**: `PUT /api/v1/user/phone`
- **认证**: Bearer Token（必需）

#### 请求参数

```json
{
  "operation_token": "opt_xxx",
  "new_phone": "+8613900139000",
  "sms_code": "123456"
}
```

**字段说明**:

- `operation_token` (string, 必填)
  - 操作令牌
  - 通过验证旧手机号/邮箱获取

- `new_phone` (string, 必填)
  - 新手机号
  - E.164格式

- `sms_code` (string, 必填)
  - 新手机号的短信验证码

#### 成功响应 (200)

```json
{
  "phone": "139******00"
}
```

**字段说明**:

- `phone` (string) - 脱敏后的新手机号

#### 错误响应

**400 Bad Request**:

- `"验证失败，请重试"` - operation_token 无效或已过期
- `"验证码有误，请重新输入"` - 新手机号验证码不正确
- `"验证码已失效，请重新获取"` - 新手机号验证码已失效
- `"该手机号已被使用"` - 新手机号已被其他用户使用

**500 Internal Server Error**:

- `"系统错误（error_code）"` - 服务器内部错误

#### 业务说明

- 必须提供 `operation_token`（通过验证旧手机号/邮箱获取）
- 必须验证新手机号的短信验证码，验证通过后验证码立即作废
- 手机号唯一性检查
- `qiao_id` 不变
- 返回脱敏后的新手机号
