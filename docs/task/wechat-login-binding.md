# 微信小程序登录/绑定改造方案

## 目标
- 降低微信手机号接口调用成本和用户操作成本
- 以 openid 为主身份进行登录，手机号仅在首次绑定时获取
- 避免"手机号已被占用/旧微信找不到"导致的死循环，保持顺畅登录
- 一账号一微信绑定（强约束）

## 核心策略
- **两段式登录**：先检查 openid 绑定，仅新用户需授权手机号
- **自动合并账号**：手机号已有账号时，解绑旧微信并绑定当前微信，轻提示用户
- **简化实现**：不需要手机号历史记录，不需要新增数据库字段

## 业务流程

### 第一段：检查绑定状态
1. 调用 `wx.login()` 获取 login_code
2. 调用 `/auth/wechat/login` 检查 openid 是否已绑定
   - 已绑定 → 返回 access_token，直接登录成功
   - 未绑定 → 返回 `need_phone: true`，显示授权按钮

### 第二段：绑定手机号（仅未绑定时）
1. 用户点击"授权手机号"按钮
2. 调用 `wx.getPhoneNumber()` 获取 phone_code
3. 重新调用 `wx.login()` 获取新的 login_code（避免过期）
4. 调用 `/auth/wechat/bind-phone` 完成绑定
   - 新手机号 → 创建用户并绑定
   - 手机号已存在 → 自动合并账号（解绑旧微信，绑定新微信）

### 账号合并场景
当手机号已被其他微信绑定时：
1. 解绑旧微信绑定
2. 绑定当前微信到该手机号账号
3. 返回轻提示："已用该手机号的账号登录并完成微信绑定"
4. 记录审计日志

## 接口设计

### POST /auth/wechat/login
检查 openid 绑定状态

**请求**：
```json
{
  "login_code": "微信 wx.login() 返回的 code"
}
```

**响应（已绑定）**：
```json
{
  "status": "bound",
  "access_token": "...",
  "refresh_token": "...",
  "expires_in": 86400,
  "user": {
    "qiao_id": "...",
    "nickname": "...",
    "avatar_url": "..."
  },
  "needs_profile_setup": false
}
```

**响应（需要绑定）**：
```json
{
  "status": "need_phone"
}
```

### POST /auth/wechat/bind-phone
绑定手机号到当前 openid

**请求**：
```json
{
  "login_code": "新的 login_code（避免过期）",
  "phone_code": "wx.getPhoneNumber() 返回的 code"
}
```

**响应**：
```json
{
  "status": "success",
  "access_token": "...",
  "refresh_token": "...",
  "expires_in": 86400,
  "user": {
    "qiao_id": "...",
    "nickname": "...",
    "avatar_url": "..."
  },
  "needs_profile_setup": false,
  "message": "已用该手机号的账号登录并完成微信绑定",
  "account_merged": true,
  "old_wechat_unbound": true
}
```

**字段说明**：
- `message`: 提示信息，仅在合并账号时返回
- `account_merged`: 是否合并了现有账号
- `old_wechat_unbound`: 是否解绑了旧微信

## 前端交互

### 登录页面状态
1. **初始状态**：显示产品介绍和功能特性
2. **需要授权**：显示"授权手机号"按钮
3. **授权中**：按钮 loading 状态
4. **授权失败**：提示"需授权手机号以完成首次登录"，可重试

### 注意事项
- 不要自动弹出手机号授权弹窗
- 用户拒绝授权后，允许重试或返回
- login_code 过期时，自动重新获取

## 数据库设计

**无需修改数据库结构**

使用现有表：
- `users` 表：phone 字段（唯一索引）
- `user_auths` 表：(auth_type, provider_uid) 唯一索引

## 日志埋点

| 事件 | 说明 |
|------|------|
| `wechat_login_start` | 开始登录 |
| `wechat_bound_user_login` | 已绑定用户直接登录 |
| `wechat_need_phone` | 需要手机号授权 |
| `wechat_new_user_created` | 新用户创建 |
| `wechat_account_merged` | 自动合并账号 |
| `wechat_old_wechat_unbound` | 解绑旧微信 |
| `wechat_bind_success` | 绑定成功 |
| `wechat_code2session_error` | 微信接口失败 |
| `wechat_phone_api_error` | 获取手机号失败 |
| `wechat_binding_dirty_data` | 数据异常（同一openid绑定多个用户）|

## 异常处理

| 场景 | 前端提示 | HTTP状态码 |
|------|----------|-----------|
| 用户拒绝手机号授权 | "需授权手机号以完成首次登录" | - |
| wx.login() 失败 | "微信授权失败，请重试" | - |
| code2session 失败 | "微信授权失效，请重试" | 500 |
| getPhoneNumber 失败 | "获取手机号失败，请重试" | 500 |
| 国际手机号 | "暂不支持国际手机号" | 400 |
| 数据异常 | "账号异常，请联系客服" | 500 |

## 文案规范

| 场景 | 文案 |
|------|------|
| 需要授权 | "需授权手机号以完成首次登录" |
| 账号合并 | "已用该手机号的账号登录并完成微信绑定" |
| 授权失败 | "手机号授权失败，请重试" |
| 接口失败 | "微信授权失效，请重试" |

## 安全性

### 微信验证机制
- 微信 getPhoneNumber 需要用户验证身份
- 不存在"输入他人手机号"的可能性
- 无需额外短信验证码

### 账号合并安全性
- 旧微信用户下次登录将创建新账号（原账号数据保留）
- 记录详细审计日志，可追溯
- 使用数据库唯一索引防止并发冲突

## 实施计划

### 阶段 1：后端改造
- 修改 `/auth/wechat/login`：仅检查绑定状态
- 新增 `/auth/wechat/bind-phone`：实现绑定和账号合并逻辑
- 添加日志埋点

### 阶段 2：前端改造
- 实现两段式登录流程
- 添加"授权手机号"按钮
- 添加错误处理和提示

### 阶段 3：测试
- 新用户注册流程
- 老用户直接登录
- 账号合并流程
- 异常场景

### 阶段 4：上线
- 灰度发布
- 监控埋点数据
- 全量发布

## 技术决策

- [x] 接口设计：两个独立接口
- [x] 账号冲突处理：自动合并 + 轻提示
- [x] login_code 续期：前端重新获取
- [x] 一账号一微信：是（强约束）
- [x] 向后兼容：否
