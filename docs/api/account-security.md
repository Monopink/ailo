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
  "target": "+8613800138000",
  "captcha_token": "cloudflare_turnstile_token"
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

- `captcha_token` (string, 可选)
  - 当 `verify_type=phone` 时必须提供
  - 值来源于前端的人机验证组件

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

**428 Precondition Required**:

- `"需要完成人机验证后再试"` - 缺少或未通过人机验证

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

## 密码管理（规划中）

> 账号密码登录暂未开放，对应的密码设置/重置能力将在未来版本发布。

## 邮箱管理（规划中）

> 邮箱绑定、修改与解绑能力尚未开放；上述接口将在未来迭代中提供。

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

- 必须提供 `operation_token`（通过验证旧手机号/邮箱获取）
- 必须验证新手机号的短信验证码，验证通过后验证码立即作废
- 手机号唯一性检查
- `qiao_id` 不变
- 返回脱敏后的新手机号
