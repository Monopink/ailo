# 用户资料和设置接口

## 接口列表

- [获取用户资料](#获取用户资料) - `GET /api/v1/user/profile`
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
- `username` (string) - 用户可自定义，注册时默认复制qiao_id，可修改
- `nickname` (string) - 昵称
- `gender` (integer) - 性别，枚举值见：`backend/app/enums/common.py` - `Gender`
- `avatar_url` (string) - 动态生成的头像 CDN URL，基于后台存储的 `avatar_file_id`
- `bio` (string) - 个人简介
- `region` (string) - 地区

### 业务说明

- 只返回用户资料信息（profiles表内容）+ username字段
- 不包括账户安全信息（手机号、邮箱等）
- region由前端维护列表，后端只验证长度

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
  "bio": "新的个人简介",
  "region": "上海"
}
```

**字段说明**:

- `username` (string, 可选)
  - 用户自定义ID
  - 3-20个字符
  - 需要检查唯一性

- `nickname` (string, 可选)
  - 昵称
  - 2-20字符

- `gender` (integer, 可选)
  - 性别，枚举值见：`backend/app/enums/common.py` - `Gender`

- `avatar_file_id` (string, 可选)
  - 头像文件ID（例如 `file_custom_avatar_123`）
  - 通过头像上传接口获取，未提供时后端使用系统默认头像
  - 服务器会在响应中根据该ID动态生成 `avatar_url`

- `bio` (string, 可选)
  - 个人简介
  - 最多200字符

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
  "bio": "新的个人简介",
  "region": "上海"
}
```

### 错误响应

**400 Bad Request**:

- `"用户名已被使用"` - username重复
- `"用户名格式错误"` - username不符合要求
- `"昵称格式错误"` - nickname不符合要求

**500 Internal Server Error**:

- `"系统错误（error_code）"` - 服务器内部错误

### 业务说明

- **Setup 场景**：首次登录创建的账号会带有 `needs_profile_setup=true`，客户端必须在此接口提交昵称、头像、gender 等信息；当后端成功写入时会原子性地清除该标记。
- 所有字段可选，支持部分更新，前端只需传递发生变化的字段即可。
- username需要检查唯一性，不满足规则会返回 400。
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
- `username` (string) - 用户名，用于登录
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
