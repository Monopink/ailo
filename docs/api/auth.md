# 用户认证接口

## 接口列表

- [发送短信验证码](#发送短信验证码) - `POST /api/v1/auth/send-sms`
- [手机号验证](#手机号验证) - `POST /api/v1/auth/phone`
- [完成注册](#完成注册) - `POST /api/v1/auth/complete-registration`
- [微信登录](#微信登录) - `POST /api/v1/auth/wechat/login`
- [账号密码登录](#账号密码登录) - `POST /api/v1/auth/login`
- [退出登录](#退出登录) - `POST /api/v1/auth/logout`

---

## 发送短信验证码

### 基本信息

- **路径**: `POST /api/v1/auth/send-sms`
- **认证**: 无需认证
- **速率限制**: 1次/60秒（同一号码）

### 请求参数

```json
{
  "phone": "+8613800138000",
  "captcha_token": "cloudflare_turnstile_token"
}
```

**字段说明**:

- `phone` (string, 必填)
  - E.164格式手机号
  - 前端可传入 `13800138000` 或 `+8613800138000`，后端自动规范化
  - MVP阶段只支持+86（中国大陆）手机号

- `captcha_token` (string, 必填)
  - 人机验证token
  - 使用 Cloudflare Turnstile 或其他验证服务

### 成功响应 (200)

```json
{
  "expires_in": 300,
  "cooldown_seconds": 60
}
```

**字段说明**:

- `expires_in` (integer) - 验证码有效期（秒）
- `cooldown_seconds` (integer) - 冷却时间（秒），用于客户端倒计时

### 错误响应

**400 Bad Request**:

- `"请30秒后再试"` - 超过速率限制

**428 Precondition Required**:

- `"需要完成人机验证后再试"` - 缺少或未通过人机验证

**500 Internal Server Error**:

- `"系统错误"` - 服务器内部错误

### 业务说明

- 需要人机验证（CAPTCHA）防止滥用
- 当系统开启 CAPTCHA 时，缺少或验证失败将返回 428，并附带 `CAPTCHA_REQUIRED` 错误信息
- 服务端强制验证速率限制
- 返回冷却时间供客户端倒计时显示
- 支持白名单号码（不受速率限制，用于测试）

---

## 手机号验证

### 基本信息

- **路径**: `POST /api/v1/auth/phone`
- **认证**: 无需认证
- **说明**: 统一登录注册入口，用户无需区分登录和注册

### 请求参数

```json
{
  "phone": "+8613800138000",
  "sms_code": "123456",
  "wechat_code": "wx_code_for_binding"
}
```

**字段说明**:

- `phone` (string, 必填)
  - E.164格式手机号
  - 前端可传入 `13800138000` 或 `+8613800138000`，后端自动规范化
  - MVP阶段只支持+86手机号

- `sms_code` (string, 必填)
  - 6位短信验证码

- `wechat_code` (string, 可选)
  - 微信绑定场景需要
  - 从微信登录接口获取的临时code

### 成功响应 - 已注册用户 (200)

```json
{
  "is_new_user": false,
  "token": "jwt_token_here",
  "user": {
    "qiao_id": "qiao_abc123",
    "phone": "138******00",
    "nickname": "小雨",
    "gender": 2,
    "avatar_url": "assets://1234",
    "bio": "个人简介"
  }
}
```

### 成功响应 - 未注册用户 (200)

```json
{
  "is_new_user": true,
  "verified_phone_token": "temp_token_xxx",
  "phone": "+8613800138000"
}
```

**字段说明**:

- `is_new_user` (boolean) - 是否为新用户
- `token` (string) - JWT token（已注册用户）
- `verified_phone_token` (string) - 临时凭证（未注册用户），有效期5分钟
- `user` (object) - 用户信息（已注册用户）

### 错误响应

**400 Bad Request**:

- `"验证码错误"` - 验证码不正确
- `"验证码已过期"` - 验证码已失效

**500 Internal Server Error**:

- `"系统错误"` - 服务器内部错误

### 业务说明

**统一登录注册入口**:

- 用户无需区分登录和注册，系统自动判断
- 已注册用户：直接返回token和用户信息，前端保存token后跳转到聊天列表
- 未注册用户：返回临时凭证，前端跳转到资料填写页

**微信绑定场景**:

- 当微信登录返回国际手机号时，需要绑定+86手机号
- 此时传入 `wechat_code` 参数
- 用户创建时会自动绑定微信openid

---

## 完成注册

### 基本信息

- **路径**: `POST /api/v1/auth/complete-registration`
- **认证**: 需要 verified_phone_token
- **说明**: 填写资料完成注册，注册和填写资料是整体事务

### 请求参数

```json
{
  "verified_phone_token": "temp_token_xxx",
  "nickname": "小雨",
  "gender": 2,
  "bio": "个人简介",
  "avatar_url": "assets://1234"
}
```

**字段说明**:

- `verified_phone_token` (string, 必填)
  - 从手机号验证接口获取的临时凭证
  - 有效期5分钟

- `nickname` (string, 必填)
  - 昵称
  - 2-20字符，支持中英文、数字、下划线

- `gender` (integer, 可选)
  - 性别，枚举值见：`backend/app/enums/common.py` - `Gender`

- `bio` (string, 可选)
  - 个人简介
  - 最多200字符

- `avatar_url` (string, 可选)
  - 头像URL
  - 使用默认头像资源标识符（如 `assets://1234`）

### 成功响应 (200)

```json
{
  "token": "jwt_token_here",
  "user": {
    "qiao_id": "qiao_abc123",
    "phone": "138******00",
    "nickname": "小雨",
    "gender": 2,
    "avatar_url": "assets://1234",
    "bio": "个人简介"
  }
}
```

### 错误响应

**400 Bad Request**:

- `"临时凭证无效"` - verified_phone_token 无效或已过期
- `"昵称格式错误"` - 昵称不符合要求

**500 Internal Server Error**:

- `"系统错误"` - 服务器内部错误

### 业务说明

**注册流程**:

1. 只有完成资料填写才会创建用户
2. 如果用户在资料填写页取消，临时凭证会自动过期，不会创建用户
3. 注册成功后自动登录，返回JWT token
4. 如果手机号验证时传入了 `wechat_code`，会自动绑定微信openid

---

## 微信登录

### 基本信息

- **路径**: `POST /api/v1/auth/wechat/login`
- **认证**: 无需认证
- **说明**: 小程序微信登录

### 请求参数

```json
{
  "login_code": "wx_login_code",
  "phone_code": "wx_phone_code"
}
```

**字段说明**:

- `login_code` (string, 必填)
  - 小程序 `wx.login()` 返回的code
  - 用于获取openid

- `phone_code` (string, 必填)
  - 小程序 `getPhoneNumber` 返回的code
  - 用于获取手机号

### 成功响应 - +86手机号 (200)

```json
{
  "success": true,
  "user": {
    "qiao_id": "qiao_abc123",
    "phone": "138******00",
    "nickname": "小雨",
    "gender": 2,
    "avatar_url": "assets://1234",
    "token": "jwt_token_here"
  }
}
```

### 成功响应 - 国际手机号 (200)

```json
{
  "success": false,
  "needs_phone_binding": true,
  "wechat_code": "wx_code_for_binding",
  "message": "手机号格式无效，请绑定手机号"
}
```

**字段说明**:

- `success` (boolean) - 是否登录成功
- `needs_phone_binding` (boolean) - 是否需要绑定手机号
- `wechat_code` (string) - 用于后续绑定手机号的临时code，有效期5分钟

### 错误响应

**400 Bad Request**:

- `"微信授权失败"` - 微信接口调用失败

**500 Internal Server Error**:

- `"系统错误"` - 服务器内部错误

### 业务说明

**后端流程**:

1. 使用 `login_code` 调用微信 code2session 接口获取openid
2. 使用 `phone_code` 调用微信 getPhoneNumber 接口获取手机号
3. 检查手机号国家代码:
   - 如果是+86手机号：查找或创建用户，返回用户信息和JWT token
   - 如果是国际手机号：返回 `needs_phone_binding=true`，前端引导用户使用手机号验证接口

**与手机号验证接口的关系**:

- 当返回 `needs_phone_binding=true` 时，前端应该调用 `POST /api/v1/auth/phone` 接口
- 并传入 `wechat_code` 参数进行绑定

---

## 账号密码登录（规划中）

> 功能尚未开放。未来版本将提供用户名/邮箱/手机号+密码的登录与相关安全策略，暂不需要在客户端接入。

---

## 退出登录

### 基本信息

- **路径**: `POST /api/v1/auth/logout`
- **认证**: Bearer Token（必需）

### 请求参数

无需请求体

### 成功响应 (200)

```json
{}
```

### 业务说明

- 退出登录会使当前token失效
- 客户端应该清除本地存储的token
- 其他设备的token不受影响

---
