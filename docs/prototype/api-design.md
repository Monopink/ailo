# API接口设计文档

## 设计原则

- 使用RESTful API设计风格
- 统一的响应格式
- 外部标识符使用qiao_id，内部使用Snowflake ID
- 所有时间字段使用Unix时间戳（毫秒）
- 分页使用cursor-based pagination
- 错误信息对用户友好，不暴露内部实现
- **业务抽象优先**: API路径使用业务语义，不暴露技术实现细节
- **数据脱敏**: 敏感信息（如手机号）需要脱敏处理

## 重要设计理念

**本项目是AI拟人陪聊应用，核心目标是让用户相信这是真人交互。**

### 铁律：拟人化设计

1. **避免AI相关字眼**：在所有用户界面、API响应、提示信息中避免使用"AI"、"机器人"、"助手"等字眼
2. **一视同仁原则**：在设计和交互中将用户和AI角色一视同仁，使用统一的称谓如"联系人"、"好友"等
3. **真人化体验**：所有交互设计都要营造真人聊天的感觉，包括响应时间、语言风格、行为模式等
4. **隐藏技术细节**：对用户隐藏所有技术实现细节，如模型调用、上下文管理等
5. **禁止暴露第三方**: API路径中不应包含第三方服务名称(如LeanCloud、Aliyun等)

### 错误处理

**原则：**

- 所有 API 都要有完善的错误处理
- 错误信息不能暴露内部实现细节
- 使用统一的错误响应格式
- **对于非预期的操作错误（如访问不存在的资源），不要暴露详细信息**
  - ❌ 错误示例：`"联系人不存在"`, `"对话不存在"`, `"用户不存在"`
  - ✅ 正确示例：`"操作异常"`, 或不返回任何提示信息（直接返回空数据）
  - 原因：避免信息泄露，防止恶意用户通过错误消息探测系统状态

## 数据脱敏规则

### 手机号脱敏

**格式**: `前3位 + ****** + 后2位`

**示例**:

- `13800138000` → `138******00`
- `18612345678` → `186******78`

**应用场景**:

- 用户资料接口返回
- 个人中心显示
- 任何需要显示手机号的地方

### 邮箱脱敏

**格式**: `首字母 + *** + @ + 域名`

**示例**:

- `user@example.com` → `u***@example.com`
- `hello@gmail.com` → `h***@gmail.com`
- `a@test.com` → `a***@test.com`

**应用场景**:

- 账户信息接口返回
- 账户安全页面显示
- 任何需要显示邮箱的地方

## 通用响应格式

### 成功响应 (HTTP 200)

直接返回业务数据，无包装：

```json
{
  "qiao_id": "qiao_abc123",
  "nickname": "小明",
  "avatar_url": "assets://1234"
}
```

列表数据：

```json
[
  {"qiao_id": "qiao_001", "nickname": "小明"},
  {"qiao_id": "qiao_002", "nickname": "小红"}
]
```

分页数据：

```json
{
  "items": [
    {"qiao_id": "qiao_001", "nickname": "小明"}
  ],
  "pagination": {
    "cursor": "next_cursor_value",
    "has_more": true
  }
}
```

### 错误响应 (HTTP 4xx/5xx)

FastAPI标准格式：

```json
{
  "detail": "用户友好的错误信息"
}
```

**说明**：

- 成功响应通过HTTP状态码200表示成功，直接返回业务数据
- 错误响应通过HTTP状态码4xx/5xx表示失败，使用FastAPI标准格式
- 前端通过HTTP状态码判断请求是否成功
- **注**: 这是MVP阶段的简化设计，2.0版本将实现统一包装格式

## API认证设计

### Bearer Token认证

所有需要认证的API使用Bearer Token认证：

```http
Authorization: Bearer <token>
```

### Token管理

- Token类型：JWT (JSON Web Token)
- Token有效期：14天（可配置）
- 每种设备类型最多1个活跃Token
- Token自动延长：每次API调用更新最后活动时间
- Token存储：数据库中的user_tokens表

### 权限检查

- 资源访问权限：检查用户是否有权访问特定资源
- 联系人权限：检查用户是否有权访问特定联系人的数据

## 速率限制设计

### 短信验证码速率限制

- **速率限制**: 1次/60秒（同一号码）
- **白名单**: 支持配置白名单号码（不受限制）

**错误响应**:

```json
{
  "detail": "请30秒后再试"
}
```

### 用户认证安全限制

- **速率限制**: 10次/小时
- **失败次数限制**: 5次失败后锁定
- **锁定时长**: 15分钟
- **人机验证触发**: 3次失败后需要人机验证

**错误响应**:

```json
{
  "detail": "登录失败次数过多，请完成人机验证"
}
```

### 消息发送速率限制

- **短期限制**: 5条/10秒
- **长期限制**: 20条/分钟

### API速率限制

- **通用限制**: 100次请求/分钟/IP
- **白名单**: 支持配置白名单IP（不受限制）

## 小程序端API

### 1. 用户认证

#### 1.1 发送短信验证码

**接口**: `POST /api/v1/auth/send-sms`

**请求参数**:

```json
{
  "phone": "+8613800138000",
  "captcha_token": "cloudflare_turnstile_token"
}
```

**成功响应**:

```json
{
  "expires_in": 300,
  "cooldown_seconds": 60
}
```

**错误响应**:

```json
{
  "detail": "请30秒后再试"
}
```

**说明**:

- phone格式: E.164标准格式(+8613800138000)
- 前端可以传入13800138000或+8613800138000,后端自动规范化为E.164格式
- MVP阶段只支持+86(中国大陆)手机号
- 需要人机验证（CAPTCHA）
- 返回冷却时间供客户端倒计时
- 服务端强制验证速率限制

#### 1.2 手机号验证（统一登录注册入口）

**接口**: `POST /api/v1/auth/phone`

**请求参数**:

```json
{
  "phone": "+8613800138000",
  "sms_code": "123456",
  "wechat_code": "wx_code_for_binding"  // 可选，微信绑定场景需要
}
```

**成功响应 - 已注册用户（直接登录）**:

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

**成功响应 - 未注册用户（需要填写资料）**:

```json
{
  "is_new_user": true,
  "verified_phone_token": "temp_token_xxx",
  "phone": "+8613800138000"
}
```

**说明**:

- **统一登录注册入口**: 用户无需区分登录和注册，系统自动判断
- phone格式: E.164标准格式(+8613800138000)
- 前端可以传入13800138000或+8613800138000，后端自动规范化为E.164格式
- MVP阶段只支持+86(中国大陆)手机号
- wechat_code: 可选参数，仅在微信登录需要绑定手机号时传入
- **已注册用户**: 直接返回token和用户信息，前端保存token后跳转到聊天列表
- **未注册用户**: 返回临时凭证(verified_phone_token)，前端跳转到资料填写页
- verified_phone_token有效期5分钟，用于完成注册
- 如果有wechat_code，会在用户创建时自动绑定微信openid

#### 1.3 完成注册（填写资料）

**接口**: `POST /api/v1/auth/complete-registration`

**请求参数**:

```json
{
  "verified_phone_token": "temp_token_xxx",
  "nickname": "小雨",  // 必填，2-20字符
  "gender": 2,  // 可选: 0=未知, 1=男, 2=女
  "bio": "个人简介",  // 可选，最多200字符
  "avatar_url": "assets://1234"  // 可选
}
```

**成功响应**:

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

**说明**:

- **注册和填写资料是整体事务**: 只有完成资料填写才会创建用户
- verified_phone_token: 从手机号验证接口获取的临时凭证
- nickname: 必填，2-20字符，支持中英文、数字、下划线
- gender: 可选，0=未知, 1=男, 2=女
- bio: 可选，最多200字符
- avatar_url: 可选，使用默认头像资源标识符
- **用户取消注册**: 如果用户在资料填写页取消，临时凭证会自动过期，不会创建用户
- 注册成功后自动登录，返回JWT token
- 如果手机号验证时传入了wechat_code，会自动绑定微信openid

#### 1.4 微信登录

**接口**: `POST /api/v1/auth/wechat/login`

**请求参数**:

```json
{
  "login_code": "wx_login_code",
  "phone_code": "wx_phone_code"
}
```

**成功响应 - +86手机号（直接登录）**:

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

**成功响应 - 国际手机号（需要绑定）**:

```json
{
  "success": false,
  "needs_phone_binding": true,
  "wechat_code": "wx_code_for_binding",
  "message": "手机号格式无效，请绑定手机号"
}
```

**说明**:

- login_code: 小程序wx.login()返回的code，用于获取openid
- phone_code: 小程序getPhoneNumber返回的code，用于获取手机号
- 两个code都必须在小程序端获取后传给后端
- **后端流程**:
  1. 使用login_code调用微信code2session接口获取openid
  2. 使用phone_code调用微信getPhoneNumber接口获取手机号
  3. 检查手机号国家代码:
     - 如果是+86手机号: 查找或创建用户，返回用户信息和JWT token
     - 如果是国际手机号: 返回needs_phone_binding=true，前端引导用户使用手机号验证接口
- 如果微信接口失败，返回错误，客户端引导使用手机号验证接口
- wechat_code: 用于后续绑定手机号的临时code，有效期5分钟
- **与手机号验证接口的关系**: 当返回needs_phone_binding=true时，前端应该调用`POST /api/v1/auth/phone`接口，并传入wechat_code参数

#### 1.5 账号密码登录

**接口**: `POST /api/v1/auth/login`

**请求参数**:

```json
{
  "username": "user123",  // 用户名、邮箱或手机号
  "password": "password123",
  "captcha_token": "cloudflare_turnstile_token"  // 可选，失败3次后必需
}
```

**成功响应**:

```json
{
  "token": "jwt_token_here",
  "user": {
    "qiao_id": "qiao_abc123",
    "username": "user123",
    "phone": "138******00",
    "email": "us***@example.com",
    "nickname": "小雨",
    "gender": 2,
    "avatar_url": "assets://1234"
  }
}
```

**说明**:

- username: 支持用户名、邮箱或手机号登录
- password: 用户密码
- captcha_token: 可选，失败3次后必需
- **安全限制**:
  - 速率限制: 10次/小时
  - 失败次数限制: 5次失败后锁定
  - 锁定时长: 15分钟
  - 人机验证触发: 3次失败后需要人机验证

#### 1.6 退出登录

**接口**: `POST /api/v1/auth/logout`

**请求头**: `Authorization: Bearer token`

**成功响应**:

```json
{}
```

#### 1.7 获取消息客户端认证签名

**接口**: `POST /api/v1/auth/message-client`

**请求头**: `Authorization: Bearer token`

**请求参数**:

```json
{
  "client_id": "qiao_user001"
}
```

**成功响应**:

```json
{
  "signature": "hmac_sha1_signature",
  "timestamp": 1710001111000,
  "nonce": "random_nonce_string",
  "client_id": "qiao_user001"
}
```

**说明**:

- 用于LeanCloud消息客户端认证
- 使用HMAC-SHA1算法生成签名
- 签名有效期：1小时

### 2. 用户资料

#### 2.1 获取用户资料

**接口**: `GET /api/v1/user/profile`

**请求头**: `Authorization: Bearer token`

**成功响应**:

```json
{
  "qiao_id": "qqid_abc123",
  "username": "my_custom_id",
  "nickname": "小雨",
  "gender": 2,
  "avatar_url": "assets://1234",
  "bio": "喜欢看书和旅行",
  "region": "北京"
}
```

**说明**:

- 只返回用户资料信息(profiles表内容) + username字段
- qiao_id: 系统内部ID,注册时生成,不可修改
- username: 用户可自定义的敲敲ID,注册时默认复制qiao_id,可修改,显示在界面上
- 不包括账户安全信息(手机号、邮箱等)
- region由前端维护列表，后端只验证长度

#### 2.2 更新用户资料

**接口**: `PUT /api/v1/user/profile`

**请求头**: `Authorization: Bearer token`

**请求参数**:

```json
{
  "username": "new_custom_id",
  "nickname": "新昵称",
  "gender": 2,
  "avatar_url": "assets://2345",
  "bio": "新的个人简介",
  "region": "上海"
}
```

**成功响应**:

```json
{
  "qiao_id": "qqid_abc123",
  "username": "new_custom_id",
  "nickname": "新昵称",
  "gender": 2,
  "avatar_url": "assets://2345",
  "bio": "新的个人简介",
  "region": "上海"
}
```

**说明**:

- 所有字段可选
- 支持部分更新
- username: 3-20个字符,检查唯一性
- avatar_url以assets://开头时，自动设置avatar_prompt

#### 2.3 获取账户信息

**接口**: `GET /api/v1/user/account`

**请求头**: `Authorization: Bearer token`

**成功响应**:

```json
{
  "qiao_id": "qiao_abc123",
  "username": "qiao_abc123",
  "phone": "138******00",
  "email": "u***@example.com",
  "has_password": true
}
```

**说明**:

- 返回账户安全相关信息
- phone: 手机号脱敏显示(138******00)
- email: 邮箱脱敏显示(u***@example.com), 未绑定时为null
- has_password: 是否设置了密码
- username: 用于登录

#### 2.4 获取用户设置

**接口**: `GET /api/v1/user/settings`

**请求头**: `Authorization: Bearer token`

**成功响应**:

```json
{
  "notification_settings": {
    "enable_sound": true,
    "enable_vibration": true
  }
}
```

#### 2.5 更新用户设置

**接口**: `PUT /api/v1/user/settings`

**请求头**: `Authorization: Bearer token`

**请求参数**:

```json
{
  "notification_settings": {
    "enable_sound": true,
    "enable_vibration": true
  }
}
```

### 3. 账户安全管理

#### 3.1 统一验证机制

##### 3.1.1 发送验证码

**接口**: `POST /api/v1/user/verify/send-code`

**请求头**: `Authorization: Bearer token`

**请求参数**:

```json
{
  "verify_type": "phone",
  "target": "+8613800138000"
}
```

**成功响应**:

```json
{
  "cooldown": 60
}
```

**说明**:

- verify_type: "phone" | "email"
- target: 可选,默认当前用户的手机号/邮箱
- 用于修改手机号/邮箱时,可以指定新的target
- 速率限制: 60秒/次

##### 3.1.2 确认验证码

**接口**: `POST /api/v1/user/verify/confirm`

**请求头**: `Authorization: Bearer token`

**请求参数**:

```json
{
  "verify_type": "phone",
  "code": "123456"
}
```

**成功响应**:

```json
{
  "operation_token": "opt_xxx",
  "expires_in": 300
}
```

**说明**:

- 验证成功返回operation_token
- operation_token有效期5分钟
- 用于后续敏感操作

#### 3.2 密码管理

##### 3.2.1 修改密码

**接口**: `PUT /api/v1/user/password`

**请求头**: `Authorization: Bearer token`

**请求参数**:

```json
{
  "old_password": "old123456",
  "new_password": "new123456"
}
```

**成功响应**: HTTP 204 No Content

**说明**:

- 首次设置密码: old_password可选(用户无密码时)
- 修改密码: old_password必填(用户有密码时)
- 密码要求: 8-128位

##### 3.2.2 重置密码

**接口**: `POST /api/v1/user/password/reset`

**请求参数**:

```json
{
  "operation_token": "opt_xxx",
  "new_password": "new123456"
}
```

**成功响应**: HTTP 204 No Content

**说明**:

- 不需要登录状态
- 需要operation_token(通过手机号/邮箱验证获取)
- 用于忘记密码场景

#### 3.3 邮箱管理

##### 3.3.1 发送邮箱验证码

**接口**: `POST /api/v1/user/email/send-code`

**请求头**: `Authorization: Bearer token`

**请求参数**:

```json
{
  "email": "user@example.com"
}
```

**成功响应**:

```json
{
  "cooldown": 60
}
```

**说明**:

- 用于绑定/修改邮箱时发送验证码
- 速率限制: 60秒/次

##### 3.3.2 绑定邮箱

**接口**: `POST /api/v1/user/email`

**请求头**: `Authorization: Bearer token`

**请求参数**:

```json
{
  "email": "user@example.com",
  "code": "123456"
}
```

**成功响应**:

```json
{
  "email": "u***@example.com"
}
```

**说明**:

- 需要登录状态
- 需要邮箱验证码
- 邮箱唯一性检查
- 返回脱敏后的邮箱

##### 3.3.3 修改邮箱

**接口**: `PUT /api/v1/user/email`

**请求头**: `Authorization: Bearer token`

**请求参数**:

```json
{
  "operation_token": "opt_xxx",
  "new_email": "new@example.com",
  "email_code": "123456"
}
```

**成功响应**:

```json
{
  "email": "n***@example.com"
}
```

**说明**:

- 需要operation_token(验证旧手机号/邮箱)
- 需要新邮箱验证码
- 邮箱唯一性检查
- 返回脱敏后的新邮箱

##### 3.3.4 解绑邮箱

**接口**: `DELETE /api/v1/user/email`

**请求头**: `Authorization: Bearer token`

**请求参数**:

```json
{
  "operation_token": "opt_xxx"
}
```

**成功响应**: HTTP 204 No Content

**说明**:

- 需要operation_token(验证手机号/邮箱)
- 解绑后邮箱字段为null

#### 3.4 手机号管理

##### 3.4.1 修改手机号

**接口**: `PUT /api/v1/user/phone`

**请求头**: `Authorization: Bearer token`

**请求参数**:

```json
{
  "operation_token": "opt_xxx",
  "new_phone": "+8613900139000",
  "sms_code": "123456"
}
```

**成功响应**:

```json
{
  "phone": "139******00"
}
```

**说明**:

- 需要operation_token(验证旧手机号/邮箱)
- 需要新手机号验证码
- 手机号唯一性检查
- qiao_id不变
- 返回脱敏后的新手机号

### 4. 联系人管理

#### 4.1 获取联系人列表

**接口**: `GET /api/v1/contacts`

**请求头**: `Authorization: Bearer token`

**查询参数**: `?cursor=xxx&limit=20`

**成功响应**:

```json
{
  "items": [
    {
      "conv_id": "conv_xyz789",
      "im_conv_id": "system_conversation_id",
      "contact_qiao_id": "qiao_xm001",
      "contact_type": 2,
      "alias": "小萌",
      "tags": ["朋友"],
      "is_pinned": 0,
      "is_muted": 0,
      "profile": {
        "nickname": "小萌",
        "gender": 2,
        "avatar_url": "assets://8923"
      }
    }
  ],
  "pagination": {
    "cursor": "next_cursor",
    "has_more": true
  }
}
```

**说明**:

- im_conv_id: IM provider conversation ID, used for message client connection
- contact_type: 1=真人用户, 2=AI角色
- 不返回last_message（客户端本地管理）
- `im_conv_id` 来源于系统接口 `GET /api/v1/system/lc-im-conversation`，此处仅作为派生字段提供给业务页面。

#### 4.2 获取单个联系人详情

**接口**: `GET /api/v1/contacts/{conv_id}`

**请求头**: `Authorization: Bearer token`

**成功响应**:

```json
{
  "conv_id": "conv_xyz789",
  "im_conv_id": "system_conversation_id",
  "contact_qiao_id": "qiao_xm001",
  "contact_type": 2,
  "alias": "小萌",
  "tags": ["朋友"],
  "remark": "很有趣的聊天伙伴",
  "is_pinned": 0,
  "is_muted": 0,
  "is_blocked": 0,
  "profile": {
    "nickname": "小萌",
    "gender": 2,
    "avatar_url": "assets://8923",
    "bio": "喜欢音乐和电影",
    "region": "上海"
  }
}
```

#### 4.3 更新联系人信息

**接口**: `PUT /api/v1/contacts/{conv_id}`

**请求头**: `Authorization: Bearer token`

**请求参数**:

```json
{
  "alias": "新的备注名",
  "tags": ["新标签1", "新标签2"],
  "remark": "新的备注信息",
  "is_pinned": 1,
  "is_muted": 0
}
```

#### 4.4 屏蔽联系人

**接口**: `POST /api/v1/contacts/{conv_id}/block`

**请求头**: `Authorization: Bearer token`

#### 4.5 取消屏蔽联系人

**接口**: `POST /api/v1/contacts/{conv_id}/unblock`

**请求头**: `Authorization: Bearer token`

#### 4.6 删除联系人

**接口**: `DELETE /api/v1/contacts/{conv_id}`

**请求头**: `Authorization: Bearer token`

**说明**:

- 删除联系人关系
- 不删除聊天记录（客户端本地管理）

#### 4.7 获取对话信息

**接口**: `GET /api/v1/contacts/{conv_id}/conversation`

**请求头**: `Authorization: Bearer token`

**成功响应**:

```json
{
  "conv_id": "conv_xyz789",
  "im_conv_id": "system_conversation_id",
  "contact_qiao_id": "qiao_xm001",
  "contact_type": 2,
  "contact_info": {
    "nickname": "小萌",
    "avatar_url": "assets://8923",
    "gender": 2
  }
}
```

**说明**:

- im_conv_id与contacts接口返回的值一致
- 此接口提供额外的联系人信息用于对话初始化
- `im_conv_id` 仍然来自系统注册表，前端的 `ConversationStore` 需要使用 `/api/v1/system/lc-im-conversation` 保持同步。

#### 4.8 获取历史消息

**接口**: `GET /api/v1/contacts/{conv_id}/messages`

**请求头**: `Authorization: Bearer token`

**查询参数**: `?cursor=xxx&limit=50`

**成功响应**:

```json
{
  "items": [
    {
      "msg_id": "msg_223788765171154945",
      "from_qiao_id": "qiao_user001",
      "to_qiao_id": "qiao_xm001",
      "content": "你好",
      "message_type": 1,
      "sent_time": 1710001111000,
      "status": 1
    }
  ],
  "pagination": {
    "cursor": "next_cursor",
    "has_more": true
  }
}
```

**说明**:

- message_type: 1=TEXT, 2=TYPING_START, 3=TYPING_END, 4=CHAT_INFO, 9=NOTIFICATION
- status: 1=已发送, 2=已送达, 3=已读, 4=失败

### 5. 联系人申请

#### 4.1 发送联系人申请

**接口**: `POST /api/v1/contact-requests`

**请求头**: `Authorization: Bearer token`

**请求参数**:

```json
{
  "to_qiao_id": "qiao_xm001",
  "message": "你好，我想和你聊天",
  "alias": "小萌",
  "tags": ["朋友", "聊天"],
  "source": 1
}
```

**字段说明**:

- `to_qiao_id`: 目标用户/AI的qiao_id（必填）
- `message`: 申请消息（可选，最长500字符）
- `alias`: 备注名（可选，最长100字符）
- `tags`: 标签列表（可选）
- `source`: 请求来源（1=搜索, 2=扫码, 3=推荐, 4=群聊, 5=名片）

**成功响应**:

```json
{
  "message": "请求已发送"
}
```

**核心设计原则**:

- **统一API设计**: 无论添加AI还是真人用户，都使用同一个API
- **后端自动路由**: 后端通过查询数据库判断目标类型（先查users表，再查ai_instances表）
- **统一返回格式**: 所有请求都返回 `{"message": "请求已发送"}`，不立即创建联系人
- **防重复请求**: 相同的请求在有效期内只能有一条
  - 如果已有pending状态的请求，返回200但不创建新请求
  - 保持旧请求直到被处理或过期
- **联系人请求 vs 联系人**:
  - 发送请求时只创建 `contact_request` 记录（申请记录）
  - 接受请求后才创建 `contact` 记录（实际联系人关系）

**处理流程**:

**AI联系人请求**:

1. **联系人模块验证**：
   - 检查是否已添加该联系人（包括已删除的）
   - 如果已删除（`is_deleted=1`），恢复联系人关系，使用新的alias和tags
   - 检查AI联系人数量上限
2. **创建联系人请求记录**（`contact_request` 表，status=PENDING）
3. **转发给AI模块验证**：
   - 验证AI资料模板是否可用
   - 验证信息模板是否可用
   - AI返回同意/拒绝决策
4. **AI接受后创建联系人**：
   - 创建AI角色（从模板）
   - 创建联系人记录（`contact` 表）
   - 更新请求状态为ACCEPTED
   - 发送CHAT_INFO消息（message_type=4）
5. **返回统一响应**: `{"message": "请求已发送"}`

**用户联系人请求**:

1. **联系人模块验证**：
   - 检查是否已添加该联系人（包括已删除的）
   - 如果已删除（`is_deleted=1`），恢复联系人关系，使用新的alias和tags
2. **创建联系人请求记录**（`contact_request` 表，status=PENDING）
3. **验证目标用户存在**
4. **发送NOTIFICATION消息**（message_type=9）给目标用户
5. **返回统一响应**: `{"message": "请求已发送"}`

**联系人恢复逻辑**:

- 如果联系人关系存在且 `is_deleted=1`，则恢复联系人
- 使用新的alias和tags，不保留旧的remark
- 保留原有的conv_id
- 返回 `{"message": "请求已发送"}`

**错误处理**:

- 400: 已添加该联系人、联系人数量已达上限、添加失败
- 500: 系统错误

**通知消息示例**:

```json
{
  "message_type": 9,
  "conv_id": "",
  "content": {
    "notification_type": 1,
    "action": {
      "type": "navigate",
      "target": "contact_requests"
    },
    "data": {
      "request_id": 123,
      "from_qiao_id": "qiao_user002",
      "from_nickname": "小红",
      "from_avatar": "assets://2345",
      "message": "你好，我想加你为好友"
    }
  }
}
```

**存储说明**:

- 通知消息（message_type=9）存入 `notification_push_history` 表
- 不存入 `message_history` 表
- 聊天信息消息（message_type=4）存入 `message_history` 表

#### 4.2 获取联系人申请列表

**接口**: `GET /api/v1/contact-requests`

**请求头**: `Authorization: Bearer token`

**查询参数**: `?status=1&cursor=xxx&limit=20`

**成功响应**:

```json
{
  "items": [
    {
      "id": 123,
      "from_qiao_id": "qiao_user001",
      "from_type": 1,
      "message": "你好，我想加你为好友",
      "status": 1,
      "created_at": 1710001111000,
      "from_profile": {
        "nickname": "小明",
        "avatar_url": "assets://1234",
        "gender": 1
      }
    }
  ],
  "pagination": {
    "cursor": "next_cursor",
    "has_more": true
  }
}
```

**字段说明**:

- `status`: 请求状态（1=待处理, 2=已接受, 3=已忽略, 4=已过期, 5=已拒绝）
- `from_type`: 申请人类型（1=真人用户, 2=AI角色, 3=官方账号）

#### 4.3 接受联系人申请

**接口**: `POST /api/v1/contact-requests/{id}/accept`

**请求头**: `Authorization: Bearer token`

**请求参数**:

```json
{
  "alias": "小明",
  "tags": ["同事"]
}
```

**成功响应**:

```json
{
  "conv_id": "conv_xyz789",
  "im_conv_id": "system_conversation_id",
  "contact_qiao_id": "qiao_user001",
  "contact_type": 1,
  "alias": "小明",
  "tags": {"tags": ["同事"]},
  "remark": null,
  "is_pinned": false,
  "is_muted": false,
  "is_blocked": false,
  "is_deleted": false,
  "created_at": "2025-01-20T10:00:00Z",
  "updated_at": "2025-01-20T10:00:00Z",
  "contact_id": 456
}
```

**说明**:

- 接受后创建联系人记录
- 发送NOTIFICATION消息给申请人
- 返回完整的ContactResponse

#### 4.4 拒绝联系人申请

**接口**: `POST /api/v1/contact-requests/{id}/reject`

**请求头**: `Authorization: Bearer token`

**成功响应**:

```json
{
  "message": "已拒绝"
}
```

**说明**:

- 更新请求状态为已拒绝
- 不发送通知给申请人

### 6. 发现页面

#### 5.1 获取广场随机联系人

**接口**: `GET /api/v1/discovery/square`

**请求头**: `Authorization: Bearer token`

**查询参数**: `?category=1&force_refresh=false`

**配置项**（system_configs）:

| 配置键 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| square_recommend_count | NUMBER | 10 | 每次推荐的联系人数量 |
| square_refresh_interval | NUMBER | 60 | 刷新间隔（秒），防止频繁刷新 |

**成功响应**:

```json
{
  "items": [
    {
      "qiao_id": "qiao_xm001",
      "category": "1",
      "nickname": "小萌",
      "gender": 2,
      "avatar_url": "assets://8923",
      "bio": "喜欢音乐和电影",
      "tags": ["音乐", "电影"],
      "region": "上海"
    }
  ],
  "refresh_available_at": "2024-01-01T12:01:00Z"
}
```

**错误响应**:

```json
{
  "detail": "刷新过于频繁，请稍后再试"
}
```

**说明**:

- 每次返回随机的AI联系人列表
- 推荐数量由`square_recommend_count`配置控制
- 刷新频率由`square_refresh_interval`配置控制
- force_refresh=true可跳过频率限制（测试用）
- refresh_available_at: 下次可刷新的时间（ISO 8601格式）
- 频率限制错误返回HTTP 429状态码

#### 6.2 获取陌生人详情

**接口**: `GET /api/v1/discovery/profile/{qiao_id}`

**请求头**: 无需认证

**路径参数**:

- `qiao_id`: 陌生人的qiao_id

**成功响应**:

```json
{
  "qiao_id": "abc123",
  "nickname": "小乔",
  "gender": 2,
  "avatar_url": "https://example.com/avatar1.jpg",
  "bio": "我是一个友善的AI伴侣，喜欢和大家聊天",
  "region": "北京",
  "category": "1"
}
```

**错误响应**:

```json
{
  "detail": "用户不存在"
}
```

**说明**:

- 公开访问,无需认证
- 返回由 `ai_personas` 驱动的 `profiles` 视图数据（square_type_entries + profile 信息）
    - 只返回 active 状态的 persona/profile rows
    - 不返回是否已添加联系人的状态
    - 用于发现页面点击联系人后查看详情

### 7. 预设资源(2.0功能,暂不实现)

#### 7.1 获取预设头像列表

**接口**: `GET /api/v1/avatars`

**请求头**: `Authorization: Bearer token`

**查询参数**: `?category=1`

**成功响应**:

```json
{
  "avatars": [
    {
      "name": "1234",
      "category": 1,
      "url": "assets://1234",
      "description": "默认头像1",
      "sort_order": 1
    }
  ]
}
```

**说明**:

- MVP阶段使用hardcode的默认头像
- 头像文件内置在小程序中
- avatar_url格式: assets://1234, assets://2345等
- 2.0功能: 管理后台可动态添加新头像

### 8. 系统配置

#### 8.1 获取 LeanCloud 系统会话 ID

**接口**: `GET /api/v1/system/lc-im-conversation`

**请求头**: `Authorization: Bearer token`

**成功响应**:

```json
{
  "im_conv_id": "system_conversation_id"
}
```

**说明**:

- 作为系统级 IM 注册表。前端 `ConversationStore`、消息服务重连流程必须通过该接口获取最新的 LeanCloud 会话 ID。
- 返回值目前仅包含 `im_conv_id`；若未来需要下发其他元数据（版本号、过期时间等），将在同一接口扩展字段。
- Contact/Conversation 等业务接口中的 `im_conv_id` 均派生自此配置，仅用于 UI 兜底，不能替代本接口。*** End Patch***}):

### 9. Webhook

#### 9.1 接收LeanCloud消息推送

**接口**: `POST /api/v1/webhook/leancloud/{webhook_token}`

**说明**:

- webhook_token: 安全令牌，防止伪造请求
- 由LeanCloud服务器调用
- 处理消息接收、消息状态更新等事件
