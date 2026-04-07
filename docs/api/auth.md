# 用户认证接口

## 接口列表

- [发送短信验证码](#发送短信验证码) - `POST /api/v1/auth/send-sms`
- [手机号登录](#手机号登录) - `POST /api/v1/auth/phone`
- [微信登录](#微信登录) - `POST /api/v1/auth/wechat/login`
- [微信手机号绑定](#2-绑定手机号) - `POST /api/v1/auth/wechat/bind-phone`
- [微信手机号更新](#微信手机号更新) - `POST /api/v1/auth/wechat/refresh-phone`
- [账号密码登录](#账号密码登录) - `POST /api/v1/auth/login`
- [刷新令牌](#刷新令牌) - `POST /api/v1/auth/refresh-token`
- [退出登录](#退出登录) - `POST /api/v1/auth/logout`

> **登录统一约束**：所有登录签发接口都必须上送 `device_id`（UUID）并稳定复用；`device_id` 生成与持久化规范见 `../spec/client/base/device-id.md`。

---

## 发送短信验证码

### 基本信息

- **路径**: `POST /api/v1/auth/send-sms`
- **认证**: 无需认证
- **速率限制**: 受限流保护

### 请求参数

```json
{
  "phone": "+8613800138000"
}
```

**字段说明**:

- `phone` (string, 必填)
  - E.164格式手机号
  - 前端可传入 `13800138000` 或 `+8613800138000`，后端自动规范化
  - 当前仅支持 +86（中国大陆）手机号

### 成功响应 (200)

```json
{
  "expires_in": 300,
  "cooldown_seconds": 60
}
```

**字段说明**:

- `expires_in` (integer) - 验证码有效期（秒），由服务端配置决定
- `cooldown_seconds` (integer) - 冷却时间（秒），用于客户端倒计时

### 错误响应

**400 Bad Request**:

- `"手机号格式无效"` - 手机号格式错误
- `"仅支持中国大陆手机号"` - 非中国大陆手机号
- `"请30秒后再试"` - 触发限流保护

**500 Internal Server Error**:

- `"系统错误（error_code）"` - 服务器内部错误

---

## 手机号登录

### 基本信息

- **路径**: `POST /api/v1/auth/phone`
- **认证**: 无需认证
- **说明**: 统一登录注册入口，所有用户都会在此接口完成账号创建与登录

### 请求参数

```json
{
  "phone": "+8613800138000",
  "sms_code": "123456",
  "device_id": "33333333-3333-3333-3333-333333333333"
}
```

**字段说明**:

- `phone` (string, 必填)
  - E.164格式手机号
  - 前端可传入 `13800138000` 或 `+8613800138000`，后端自动规范化
  - 当前仅支持 +86（中国大陆）手机号

- `sms_code` (string, 必填)
  - 短信验证码固定为 6 位

- `device_id` (string, 必填)
  - 设备/安装级 UUID
  - 必须稳定持久化并在同一设备复用

### 成功响应 (200)

```json
{
  "access_token": "jwt_token_here",
  "refresh_token": "refresh_token_here",
  "expires_in": 86400,
  "needs_profile_setup": true,
  "user": {
    "qiao_id": "qiao_abc123",
    "phone": "138******00",
    "nickname": "小雨",
    "gender": 2,
    "avatar_url": "https://cdn.example.com/profiles/qiao_abc123.webp",
    "bio": "个性签名"
  }
}
```

**字段说明**:

- `access_token` (string) - JWT 访问令牌
- `refresh_token` (string) - 刷新令牌
- `expires_in` (integer) - Access Token 有效期（秒）
- `needs_profile_setup` (boolean) - 是否需要跳转到 Setup 页面完善资料；新创建的账号默认为 true
- `user` (object) - 当前用户资料
  - `avatar_url` 由服务器基于 `avatar_file_id` 动态生成（CDN URL），不会在数据库中以明文字段保存

### 错误响应

**400 Bad Request**:

- `"验证码有误，请重新输入"` - 验证码不正确
- `"验证码已失效，请重新获取"` - 验证码已失效
- `"手机号格式无效"` - 手机号格式错误
- `"仅支持中国大陆手机号"` - 非中国大陆手机号
- `"账号已被禁用"`

**500 Internal Server Error**:

- `"系统错误（error_code）"` - 服务器内部错误

### 业务说明

- **登录注册合一**：手机号首次登录会自动创建 `users` 与 `profiles` stub，并立即返回 JWT；之后再次登录将复用同一个账号。
- **默认昵称生成**：当首次创建 `profiles` stub 且客户端未提交昵称时，服务端按 `system_configs.default_nickname_prefix + 随机大写字母后缀` 生成昵称；后缀长度由 `system_configs.default_nickname_suffix_length` 控制。
- **资料补全标记**：`needs_profile_setup=true` 时客户端需要强制跳转到 Setup 页面，通过 `PUT /api/v1/user/profile` 填写昵称、头像等信息，完成后该标记会被清零。

## 微信登录（两段式）

### 1) 检查绑定状态

- **路径**: `POST /api/v1/auth/wechat/login`
- **认证**: 无需认证
- **说明**: 使用 `login_code + device_id` 检查 openid 是否已有绑定；若已绑定会直接签发 JWT

**请求参数**

```json
{
  "login_code": "wx_login_code",
  "device_id": "33333333-3333-3333-3333-333333333333"
}
```

字段说明：

- `login_code` (string, 必填) - 来自 `wx.login()`
- `device_id` (string, 必填) - 设备/安装级 UUID（稳定复用）

**响应（已绑定）**

```json
{
  "status": "bound",
  "access_token": "jwt_token_here",
  "refresh_token": "refresh_token_here",
  "expires_in": 86400,
  "needs_profile_setup": false,
  "user": {
    "qiao_id": "qiao_abc123",
    "nickname": "小雨",
    "avatar_url": "https://cdn.example.com/profiles/qiao_abc123.webp"
  },
  "message": "登录成功"
}
```

**响应（需要手机号绑定）**

```json
{
  "status": "need_phone"
}
```

**错误响应**

- `400 Bad Request`
  - `"账号异常，请联系客服"` - openid 绑定数据异常
  - `"账号已被禁用"`
- `500 Internal Server Error`
  - `"微信服务异常,请稍后再试"`
  - `"登录失败,请稍后再试"`

### 2) 绑定手机号

- **路径**: `POST /api/v1/auth/wechat/bind-phone`
- **认证**: 无需认证
- **说明**: 仅在 `status=need_phone` 时调用，完成手机号绑定并登录；单接口同时支持新旧两种微信手机号授权载荷

**请求参数（新协议：code）**

```json
{
  "login_code": "wx_login_code",
  "phone_code": "wx_phone_code",
  "device_id": "33333333-3333-3333-3333-333333333333"
}
```

字段说明：

- `login_code` (string, 必填) - 来自 `wx.login()`
- `phone_code` (string, 必填) - 来自 `getPhoneNumber`
- `device_id` (string, 必填) - 设备/安装级 UUID（稳定复用）

**请求参数（兼容协议：encryptedData + iv）**

```json
{
  "login_code": "wx_login_code",
  "encrypted_data": "wx_encrypted_data",
  "iv": "wx_iv",
  "device_id": "33333333-3333-3333-3333-333333333333"
}
```

字段说明：

- `login_code` (string, 必填) - 来自 `wx.login()`
- `encrypted_data` (string, 必填) - 来自 `getPhoneNumber` 回调
- `iv` (string, 必填) - 来自 `getPhoneNumber` 回调
- `device_id` (string, 必填) - 设备/安装级 UUID（稳定复用）

**成功响应 (200)**

```json
{
  "status": "success",
  "access_token": "jwt_token_here",
  "refresh_token": "refresh_token_here",
  "expires_in": 86400,
  "needs_profile_setup": false,
  "user": {
    "qiao_id": "qiao_abc123",
    "nickname": "小雨",
    "avatar_url": "https://cdn.example.com/profiles/qiao_abc123.webp"
  },
  "message": "已用该手机号的账号登录并完成微信绑定",
  "binding_reused": true,
  "replaced_old_wechat": true
}
```

**错误响应**

- `400 Bad Request`
  - `"暂不支持国际手机号"`
  - `"手机号格式无效"`
  - `"账号已被禁用"`
- `500 Internal Server Error`
  - `"微信服务异常,请稍后再试"`
  - `"绑定失败，请稍后再试"`

**业务说明**

- 该接口只在用户同意手机号授权后调用。
- `device_id` 必须稳定复用；生成与持久化规范见 `../spec/client/base/device-id.md`。
- `phone_code` 与 `encrypted_data + iv` 为互斥协议载荷，调用时二选一。
- 仅支持中国大陆手机号；国际号码直接返回 400。
- 手机号已存在时会解绑旧微信并绑定到当前微信，轻提示用户；旧微信下次按未绑定流程处理，无需特殊分支。
- 开发/测试环境可启用虚拟手机号 Mock（生产环境关闭）；当启用时，微信手机号授权将返回固定手机号。

## 微信手机号更新

> 已登录用户通过微信授权重新绑定手机号。

### 基本信息

- **路径**: `POST /api/v1/auth/wechat/refresh-phone`
- **认证**: Bearer Token（必需）

### 请求参数

```json
{
  "login_code": "wx_login_code",
  "phone_code": "wx_phone_code"
}
```

### 成功响应 (200)

```json
{
  "phone": "138******00",
  "user": {
    "qiao_id": "qiao_abc123",
    "phone": "138******00",
    "nickname": "小雨",
    "gender": 2,
    "avatar_url": "https://cdn.example.com/profiles/qiao_abc123.webp"
  }
}
```

### 错误响应

**400 Bad Request**:

- "微信授权失败" - 微信接口调用失败
- "暂不支持国际手机号" - 微信返回的手机号不是中国大陆号码
- "手机号格式无效" - 微信返回的手机号格式异常

**409 Conflict**:

- "该手机号已被使用" - 新手机号已被其他账号占用
- "该微信已绑定其它账号" - code2session 返回的 openid 与当前账号不匹配

**500 Internal Server Error**:

- "系统错误（error_code）" - 服务器内部错误

### 业务说明

- 客户端需重新调用 `wx.login()` 与 `getPhoneNumber` 获取 `login_code`、`phone_code`；
- 接口会验证 openid 与当前账号的绑定关系，不允许交叉绑定；
- 与登录接口相同，`login_code` 与 `phone_code` 必须同时有效；用户拒绝授权时直接在前端提示“需要授权手机号才能更新”。
- 更新成功后返回脱敏手机号及最新的用户信息，等同于重新登录后的 `user` 结构；
- 该接口是小程序手机号更新方式，不需要短信验证码。

## 账号密码登录

### 基本信息

- **路径**: `POST /api/v1/auth/login`
- **认证**: 无需认证
- **说明**: 使用 username / phone / email + password 登录并签发 JWT

### 请求体

```json
{
  "identifier": "alice",
  "password": "password_here",
  "device_id": "33333333-3333-3333-3333-333333333333",
  "device_type": 3
}
```

字段说明：

- `identifier` (string, 必填)：登录标识，服务端自动识别
  - 包含 `@`：按 email 登录
  - 纯数字：按 phone 登录
  - 其他：按 username 登录
- `password` (string, 必填)：密码明文（HTTPS 传输）
- `device_id` (string, 必填)：设备/安装级 UUID（用于离线消息游标与端点管理）
- `device_type` (int, 必填)：设备类型（见 `backend/app/enums/` - `DeviceType`）

### 成功响应 (200)

```json
{
  "access_token": "jwt_token_here",
  "refresh_token": "refresh_token_here",
  "expires_in": 86400,
  "needs_profile_setup": false,
  "user": {
    "qiao_id": "qiao_abc123",
    "nickname": "小雨",
    "avatar_url": "https://cdn.example.com/profiles/qiao_abc123.webp"
  }
}
```

### 错误响应

- `400 Bad Request`
  - `"账号或密码错误"`
- `400 Bad Request`
  - `"账号已被禁用"`
- `400 Bad Request`
  - 风控命中不会使用专用错误码；对外复用 Auth 模块常见可纠正错误码（与普通错误同态）

### 业务说明

- 登录成功后，客户端使用 `access_token` 访问需要认证的 API。
- `device_id` 必须稳定持久化；见 `../spec/client/base/device-id.md`。
- username 规则见 `../spec/user/username.md`。

---

## 刷新令牌

### 基本信息

- **路径**: `POST /api/v1/auth/refresh-token`
- **认证**: 无需认证
- **说明**: 使用 `refresh_token` 换取新的 `access_token`

### 请求体

```json
{
  "refresh_token": "refresh_token_here"
}
```

### 成功响应 (200)

```json
{
  "access_token": "jwt_token_here",
  "expires_in": 86400
}
```

### 错误响应

- `400 Bad Request`
  - `"登录已失效，请重新登录"`
- `401 Unauthorized`
  - `"登录失效"`
- `500 Internal Server Error`
  - `"系统错误（error_code）"`

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
