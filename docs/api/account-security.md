# 账户安全管理接口

## 接口列表

- [发送验证码](#发送验证码) - `POST /api/v1/user/verify/send-code`
- [确认验证码](#确认验证码) - `POST /api/v1/user/verify/confirm`
- [修改密码](#修改密码) - `PUT /api/v1/user/password`
- [重置密码](#重置密码) - `POST /api/v1/user/password/reset`
- [发送邮箱验证码](#发送邮箱验证码) - `POST /api/v1/user/email/send-code`
- [绑定邮箱](#绑定邮箱) - `POST /api/v1/user/email`
- [修改邮箱](#修改邮箱) - `PUT /api/v1/user/email`
- [解绑邮箱](#解绑邮箱) - `DELETE /api/v1/user/email`
- [修改手机号](#修改手机号) - `PUT /api/v1/user/phone`

---

## 统一验证机制

### 发送验证码

#### 基本信息

- **路径**: `POST /api/v1/user/verify/send-code`
- **认证**: Bearer Token（必需）
- **速率限制**: 60秒/次

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
  - 可选值: `phone` | `email`

- `target` (string, 可选)
  - 目标手机号或邮箱
  - 默认为当前用户的手机号/邮箱
  - 用于修改手机号/邮箱时，可以指定新的target

#### 成功响应 (200)

```json
{
  "cooldown": 60
}
```

**字段说明**:

- `cooldown` (integer) - 冷却时间（秒）

#### 错误响应

**429 Too Many Requests**:

- `"请60秒后再试"` - 超过速率限制

**500 Internal Server Error**:

- `"系统错误"` - 服务器内部错误

---

### 确认验证码

#### 基本信息

- **路径**: `POST /api/v1/user/verify/confirm`
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
  - 可选值: `phone` | `email`

- `code` (string, 必填)
  - 6位验证码

#### 成功响应 (200)

```json
{
  "operation_token": "opt_xxx",
  "expires_in": 300
}
```

**字段说明**:

- `operation_token` (string) - 操作令牌，用于后续敏感操作
- `expires_in` (integer) - 有效期（秒），默认5分钟

#### 错误响应

**400 Bad Request**:

- `"验证码错误"` - 验证码不正确
- `"验证码已过期"` - 验证码已失效

**500 Internal Server Error**:

- `"系统错误"` - 服务器内部错误

#### 业务说明

- 验证成功返回 `operation_token`
- `operation_token` 有效期5分钟
- 用于后续敏感操作（修改密码、修改手机号、修改邮箱等）

---

## 密码管理

### 修改密码

#### 基本信息

- **路径**: `PUT /api/v1/user/password`
- **认证**: Bearer Token（必需）

#### 请求参数

```json
{
  "old_password": "old123456",
  "new_password": "new123456"
}
```

**字段说明**:

- `old_password` (string, 可选)
  - 旧密码
  - 首次设置密码时可选（用户无密码时）
  - 修改密码时必填（用户有密码时）

- `new_password` (string, 必填)
  - 新密码
  - 8-128位

#### 成功响应 (204)

无返回内容

#### 错误响应

**400 Bad Request**:

- `"旧密码错误"` - 旧密码不正确
- `"密码格式错误"` - 新密码不符合要求

**500 Internal Server Error**:

- `"系统错误"` - 服务器内部错误

#### 业务说明

- 首次设置密码：`old_password` 可选
- 修改密码：`old_password` 必填
- 密码要求：8-128位

---

### 重置密码

#### 基本信息

- **路径**: `POST /api/v1/user/password/reset`
- **认证**: 无需认证
- **说明**: 用于忘记密码场景

#### 请求参数

```json
{
  "operation_token": "opt_xxx",
  "new_password": "new123456"
}
```

**字段说明**:

- `operation_token` (string, 必填)
  - 操作令牌
  - 通过手机号/邮箱验证获取

- `new_password` (string, 必填)
  - 新密码
  - 8-128位

#### 成功响应 (204)

无返回内容

#### 错误响应

**400 Bad Request**:

- `"操作令牌无效"` - operation_token 无效或已过期
- `"密码格式错误"` - 新密码不符合要求

**500 Internal Server Error**:

- `"系统错误"` - 服务器内部错误

#### 业务说明

- 不需要登录状态
- 需要 `operation_token`（通过手机号/邮箱验证获取）
- 用于忘记密码场景

---

## 邮箱管理

### 发送邮箱验证码

#### 基本信息

- **路径**: `POST /api/v1/user/email/send-code`
- **认证**: Bearer Token（必需）
- **速率限制**: 60秒/次

#### 请求参数

```json
{
  "email": "user@example.com"
}
```

**字段说明**:

- `email` (string, 必填)
  - 邮箱地址
  - 用于绑定/修改邮箱时发送验证码

#### 成功响应 (200)

```json
{
  "cooldown": 60
}
```

#### 错误响应

**429 Too Many Requests**:

- `"请60秒后再试"` - 超过速率限制

**500 Internal Server Error**:

- `"系统错误"` - 服务器内部错误

---

### 绑定邮箱

#### 基本信息

- **路径**: `POST /api/v1/user/email`
- **认证**: Bearer Token（必需）

#### 请求参数

```json
{
  "email": "user@example.com",
  "code": "123456"
}
```

**字段说明**:

- `email` (string, 必填)
  - 邮箱地址

- `code` (string, 必填)
  - 6位邮箱验证码

#### 成功响应 (200)

```json
{
  "email": "u***@example.com"
}
```

**字段说明**:

- `email` (string) - 脱敏后的邮箱

#### 错误响应

**400 Bad Request**:

- `"验证码错误"` - 验证码不正确
- `"邮箱已被使用"` - 邮箱已被其他用户绑定

**500 Internal Server Error**:

- `"系统错误"` - 服务器内部错误

#### 业务说明

- 需要登录状态
- 需要邮箱验证码
- 邮箱唯一性检查
- 返回脱敏后的邮箱

---

### 修改邮箱

#### 基本信息

- **路径**: `PUT /api/v1/user/email`
- **认证**: Bearer Token（必需）

#### 请求参数

```json
{
  "operation_token": "opt_xxx",
  "new_email": "new@example.com",
  "email_code": "123456"
}
```

**字段说明**:

- `operation_token` (string, 必填)
  - 操作令牌
  - 通过验证旧手机号/邮箱获取

- `new_email` (string, 必填)
  - 新邮箱地址

- `email_code` (string, 必填)
  - 新邮箱的验证码

#### 成功响应 (200)

```json
{
  "email": "n***@example.com"
}
```

**字段说明**:

- `email` (string) - 脱敏后的新邮箱

#### 错误响应

**400 Bad Request**:

- `"操作令牌无效"` - operation_token 无效或已过期
- `"验证码错误"` - 新邮箱验证码不正确
- `"邮箱已被使用"` - 新邮箱已被其他用户绑定

**500 Internal Server Error**:

- `"系统错误"` - 服务器内部错误

#### 业务说明

- 需要 `operation_token`（验证旧手机号/邮箱）
- 需要新邮箱验证码
- 邮箱唯一性检查
- 返回脱敏后的新邮箱

---

### 解绑邮箱

#### 基本信息

- **路径**: `DELETE /api/v1/user/email`
- **认证**: Bearer Token（必需）

#### 请求参数

```json
{
  "operation_token": "opt_xxx"
}
```

**字段说明**:

- `operation_token` (string, 必填)
  - 操作令牌
  - 通过验证手机号/邮箱获取

#### 成功响应 (204)

无返回内容

#### 错误响应

**400 Bad Request**:

- `"操作令牌无效"` - operation_token 无效或已过期

**500 Internal Server Error**:

- `"系统错误"` - 服务器内部错误

#### 业务说明

- 需要 `operation_token`（验证手机号/邮箱）
- 解绑后邮箱字段为null

---

## 手机号管理

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

- `"操作令牌无效"` - operation_token 无效或已过期
- `"验证码错误"` - 新手机号验证码不正确
- `"手机号已被使用"` - 新手机号已被其他用户使用

**500 Internal Server Error**:

- `"系统错误"` - 服务器内部错误

#### 业务说明

- 需要 `operation_token`（验证旧手机号/邮箱）
- 需要新手机号验证码
- 手机号唯一性检查
- `qiao_id` 不变
- 返回脱敏后的新手机号
