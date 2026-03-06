# 用户资料和设置接口

## 接口列表

- [获取用户资料](#获取用户资料) - `GET /api/v1/user/profile`
- [校验敲敲号](#校验敲敲号) - `GET /api/v1/user/username/check`
- [更新用户资料](#更新用户资料) - `PUT /api/v1/user/profile`
- [获取账户信息](#获取账户信息) - `GET /api/v1/user/account`
- [获取用户设置](#获取用户设置) - `GET /api/v1/user/settings`
- [更新用户设置](#更新用户设置) - `PUT /api/v1/user/settings`

---

## 获取用户资料

### 基本信息

- **路径**: `GET /api/v1/user/profile`
- **认证**: Bearer Token（必需）

### 请求参数

无需参数

### 成功响应 (200)

```json
{
  "qiao_id": "qiao_abc123",
  "username": "my_custom_id",
  "nickname": "小雨",
  "gender": 2,
  "avatar_url": "https://cdn.example.com/profiles/qiao_abc123.webp",
  "bio": "喜欢看书和旅行",
  "region": "北京"
}
```

**字段说明**:

- `qiao_id` (string) - 系统内部ID，注册时生成，不可修改
- `username` (string, nullable) - 用户敲敲号，未设置时为 `null`；首次设置成功后不可修改
- `nickname` (string) - 昵称
- `gender` (integer) - 性别，枚举值见：`backend/app/enums/common.py` - `Gender`
- `avatar_url` (string) - 动态生成的头像 CDN URL，基于后台存储的 `avatar_file_id`
- `bio` (string) - 个性签名
- `region` (string) - 地区

### 业务说明

- 只返回用户资料信息（profiles表内容）+ username字段
- 不包括账户安全信息（手机号、邮箱等）
- region由前端维护列表，后端只验证长度

---

## 校验敲敲号

### 基本信息

- **路径**: `GET /api/v1/user/username/check`
- **认证**: Bearer Token（必需）

### 请求参数

- `username` (query, string, 必填)
  - 校验规则见 `docs/spec/user/username.md`

### 成功响应 (200)

```json
{
  "available": true
}
```

### 错误响应

用户侧统一错误结构见 `docs/api/error-codes.md`，本接口业务错误会额外返回 `reason`：

```json
{
  "error_code": 13011001,
  "message": "敲敲号必须以字母开头",
  "reason": "USERNAME_MUST_START_WITH_LETTER",
  "request_id": "req_xxx"
}
```

常见 `reason`：

- `USERNAME_EMPTY`
- `USERNAME_LEADING_OR_TRAILING_SPACES`
- `USERNAME_TOO_SHORT`
- `USERNAME_TOO_LONG`
- `USERNAME_MUST_START_WITH_LETTER`
- `USERNAME_INVALID_CHARACTERS`
- `USERNAME_RESERVED`
- `USERNAME_ALREADY_USED`
- `USERNAME_CHECK_RATE_LIMIT_SHORT`
- `USERNAME_CHECK_RATE_LIMIT_LONG`
- `USERNAME_LOCKED`

---

## 更新用户资料

### 基本信息

- **路径**: `PUT /api/v1/user/profile`
- **认证**: Bearer Token（必需）

### 请求参数

```json
{
  "username": "new_custom_id",
  "nickname": "新昵称",
  "gender": 2,
  "avatar_file_id": "file_custom_avatar_123",
  "bio": "新的个性签名",
  "region": "上海"
}
```

**字段说明**:

- `username` (string, 可选)
  - 用户敲敲号（仅 `users.username` 为空时允许设置）
  - 校验规则见 `docs/spec/user/username.md`

- `nickname` (string, 可选)
  - 昵称
  - 显示宽度上限：24（约12个中文或24个英文）
  - 字符上限：32（按字符簇计数）
  - 不支持传入 `null` 或空字符串清空

- `gender` (integer, 可选)
  - 性别，枚举值见：`backend/app/enums/common.py` - `Gender`

- `avatar_file_id` (string, 可选)
  - 头像文件ID（例如 `file_custom_avatar_123`）
  - 通过头像上传接口获取，未提供时后端使用系统默认头像
  - 服务器会在响应中根据该ID动态生成 `avatar_url`

- `bio` (string, 可选)
  - 个性签名
  - 显示宽度上限：120（约60个中文或120个英文）
  - 字符上限：120（按字符簇计数）
  - 传入 `null` 可清空个性签名

- `region` (string, 可选)
  - 地区
  - 由前端维护列表

### 成功响应 (200)

```json
{
  "qiao_id": "qiao_abc123",
  "username": "new_custom_id",
  "nickname": "新昵称",
  "gender": 2,
  "avatar_url": "https://cdn.example.com/profiles/qiao_abc123.webp",
  "bio": "新的个性签名",
  "region": "上海"
}
```

### 错误响应

用户侧统一错误结构见 `docs/api/error-codes.md`。当本接口涉及 `username` 失败时，响应会额外返回 `reason` 字段，例如：

```json
{
  "error_code": 13014003,
  "message": "敲敲号不可修改",
  "reason": "USERNAME_LOCKED",
  "request_id": "req_xxx"
}
```

`username` 相关常见 `reason`：

- `USERNAME_EMPTY`
- `USERNAME_LEADING_OR_TRAILING_SPACES`
- `USERNAME_TOO_SHORT`
- `USERNAME_TOO_LONG`
- `USERNAME_MUST_START_WITH_LETTER`
- `USERNAME_INVALID_CHARACTERS`
- `USERNAME_RESERVED`
- `USERNAME_ALREADY_USED`
- `USERNAME_LOCKED`
- `USERNAME_SUBMIT_RATE_LIMIT`

### 业务说明

- **Setup 场景**：首次登录创建的账号会带有 `needs_profile_setup=true`，客户端必须在此接口提交昵称、头像、gender 等信息；当后端成功写入时会原子性地清除该标记。
- 所有字段可选，支持部分更新，前端只需传递发生变化的字段即可。
- username 仅允许首次设置；已设置后提交 `username` 一律拒绝。
- username 校验规则见 `docs/spec/user/username.md`，不满足规则会返回 400。
- avatar_url 在响应中始终由后端根据 `avatar_file_id` 生成，客户端只需要维护 `avatar_file_id` 并在上传成功后重新调用本接口即可获取最终展示 URL。

---

## 获取账户信息

### 基本信息

- **路径**: `GET /api/v1/user/account`
- **认证**: Bearer Token（必需）

### 请求参数

无需参数

### 成功响应 (200)

```json
{
  "qiao_id": "qiao_abc123",
  "username": "qiao_abc123",
  "phone": "138******00",
  "email": "u***@example.com",
  "has_password": true
}
```

**字段说明**:

- `qiao_id` (string) - 系统内部ID
- `username` (string, nullable) - 用户名，用于登录；未设置时为 `null`
- `phone` (string) - 手机号（脱敏显示）
- `email` (string, nullable) - 邮箱（脱敏显示），未绑定时为null
- `has_password` (boolean) - 是否设置了密码

### 业务说明

- 返回账户安全相关信息
- 手机号脱敏显示：`138******00`
- 邮箱脱敏显示：`u***@example.com`
- 未绑定邮箱时，email字段为null

---

## 获取用户设置

### 基本信息

- **路径**: `GET /api/v1/user/settings`
- **认证**: Bearer Token（必需）

### 请求参数

无需参数

### 成功响应 (200)

```json
{
  "notification_settings": {
    "enable_sound": true,
    "enable_vibration": true
  }
}
```

**字段说明**:

- `notification_settings` (object) - 通知设置
  - `enable_sound` (boolean) - 是否启用声音
  - `enable_vibration` (boolean) - 是否启用震动

### 业务说明

- 返回用户的个性化设置
- 设置存储在数据库中
- 不同设备可以有不同的设置

---

## 更新用户设置

### 基本信息

- **路径**: `PUT /api/v1/user/settings`
- **认证**: Bearer Token（必需）

### 请求参数

```json
{
  "notification_settings": {
    "enable_sound": true,
    "enable_vibration": true
  }
}
```

**字段说明**:

- `notification_settings` (object, 可选) - 通知设置
  - `enable_sound` (boolean) - 是否启用声音
  - `enable_vibration` (boolean) - 是否启用震动

### 成功响应 (200)

```json
{
  "notification_settings": {
    "enable_sound": true,
    "enable_vibration": true
  }
}
```

### 错误响应

**400 Bad Request**:

- `"参数错误"` - 请求参数格式错误

**500 Internal Server Error**:

- `"系统错误（error_code）"` - 服务器内部错误

### 业务说明

- 支持部分更新
- 只更新传入的字段
- 未传入的字段保持不变
