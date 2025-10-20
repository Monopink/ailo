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

## 通用响应格式

### 成功响应 (HTTP 200)

直接返回业务数据，无包装：

```json
{
  "qiao_id": "qiao_abc123",
  "nickname": "小明",
  "avatar_url": "assets://avatar_01"
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

#### 1.2 用户注册（自动登录）

**接口**: `POST /api/v1/auth/register`

**请求参数**:

```json
{
  "phone": "+8613800138000",
  "sms_code": "123456",
  "captcha_token": "cloudflare_turnstile_token"
}
```

**成功响应**:

```json
{
  "user": {
    "qiao_id": "qiao_abc123"
  },
  "session": {
    "token": "session_token_here",
    "expires_at": 1710001111000
  }
}
```

**说明**:

- phone格式: E.164标准格式(+8613800138000)
- 前端可以传入13800138000或+8613800138000,后端自动规范化为E.164格式
- MVP阶段只支持+86(中国大陆)手机号
- 注册只需要手机号和验证码
- 注册成功后自动登录，返回JWT token
- 用户资料通过单独的API设置
- 需要人机验证（CAPTCHA）

#### 1.3 微信登录

**接口**: `POST /api/v1/auth/wechat/login`

**请求参数**:

```json
{
  "login_code": "wx_login_code",
  "phone_code": "wx_phone_code"
}
```

**成功响应(+86手机号)**:

```json
{
  "user": {
    "qiao_id": "qiao_abc123"
  },
  "profile": {
    "nickname": "小雨",
    "gender": 2,
    "avatar_url": "assets://avatar_01"
  },
  "session": {
    "token": "session_token_here",
    "expires_at": 1710001111000
  },
  "is_new_user": false
}
```

**成功响应(国际手机号,需要绑定)**:

```json
{
  "needs_phone_binding": true,
  "wechat_phone": "+14155552671",
  "wechat_code": "wx_code_for_binding",
  "message": "检测到国际手机号,请绑定中国大陆手机号"
}
```

**说明**:

- login_code: 小程序wx.login()返回的code,用于获取openid
- phone_code: 小程序getPhoneNumber返回的code,用于获取手机号
- 两个code都必须在小程序端获取后传给后端
- 后端流程:
  1. 使用login_code调用微信code2session接口获取openid
  2. 使用phone_code调用微信getPhoneNumber接口获取手机号
  3. 检查手机号国家代码:
     - 如果是+86手机号: 直接注册/登录,返回用户信息和JWT token
     - 如果是国际手机号: 返回needs_phone_binding=true,前端引导用户绑定+86手机号
- 如果微信接口失败,返回错误,客户端引导使用短信验证码绑定
- 如果profile为null,客户端强制引导设置资料(nickname和gender必填)
- is_new_user: true表示新注册用户,false表示已存在用户
- wechat_code: 用于后续绑定手机号的临时code,有效期5分钟

#### 1.4 绑定手机号(回退方案)

**接口**: `POST /api/v1/auth/bind-phone`

**请求参数**:

```json
{
  "wechat_code": "wx_code_for_binding",
  "phone": "+8613800138000",
  "sms_code": "123456"
}
```

**成功响应**:

```json
{
  "user": {
    "qiao_id": "qiao_abc123"
  },
  "session": {
    "token": "session_token_here",
    "expires_at": 1710001111000
  },
  "is_new_user": true
}
```

**说明**:

- 使用场景:
  1. 微信获取手机号接口失败
  2. 微信返回国际手机号(非+86)
- phone格式: E.164标准格式(+8613800138000)
- 前端可以传入13800138000或+8613800138000,后端自动规范化为E.164格式
- MVP阶段只支持+86(中国大陆)手机号
- 需要先调用发送短信验证码接口
- 验证通过后创建用户并绑定微信openid
- 如果手机号已注册,则关联微信openid到已有账号
- 强制绑定手机号,不能跳过
- wechat_code有效期5分钟

#### 1.5 短信验证码登录

**接口**: `POST /api/v1/auth/login/sms`

**请求参数**:

```json
{
  "phone": "+8613800138000",
  "sms_code": "123456",
  "device_type": 4,
  "device_id": "device_unique_id",
  "captcha_token": "cloudflare_turnstile_token"
}
```

**成功响应**:

```json
{
  "user": {
    "qiao_id": "qiao_abc123"
  },
  "profile": {
    "nickname": "小雨",
    "gender": 2,
    "avatar_url": "assets://avatar_01"
  },
  "session": {
    "token": "session_token_here",
    "expires_at": 1710001111000
  }
}
```

**说明**:

- phone格式: E.164标准格式(+8613800138000)
- 前端可以传入13800138000或+8613800138000,后端自动规范化为E.164格式
- MVP阶段只支持+86(中国大陆)手机号
- captcha_token可选，失败3次后必需
- 如果profile为null，客户端强制引导设置资料
- device_type: 1=iOS, 2=Android, 3=Web, 4=MiniProgram

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
  "qiao_id": "qiao_abc123",
  "username": "qiao_abc123",
  "phone": "+86 138****8000",
  "nickname": "小雨",
  "gender": 2,
  "avatar_url": "assets://avatar_01",
  "bio": "喜欢看书和旅行",
  "region": "北京"
}
```

**说明**:

- phone格式: E.164格式脱敏显示(+86 138****8000)
- 手机号脱敏规则: 显示国家代码+前3位+****+后4位
- username用于登录
- region由前端维护列表，后端只验证长度

#### 2.2 更新用户资料

**接口**: `PUT /api/v1/user/profile`

**请求头**: `Authorization: Bearer token`

**请求参数**:

```json
{
  "nickname": "新昵称",
  "gender": 2,
  "avatar_url": "assets://avatar_02",
  "bio": "新的个人简介",
  "region": "上海"
}
```

**成功响应**:

```json
{
  "qiao_id": "qiao_abc123",
  "username": "qiao_abc123",
  "phone": "+86 138****8000",
  "nickname": "新昵称",
  "gender": 2,
  "avatar_url": "assets://avatar_02",
  "bio": "新的个人简介",
  "region": "上海"
}
```

**说明**:

- 所有字段可选
- avatar_url以assets://开头时，自动设置avatar_prompt

#### 2.3 获取用户设置

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

#### 2.4 更新用户设置

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

### 3. 联系人管理

#### 3.1 获取联系人列表

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

#### 3.2 获取单个联系人详情

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

#### 3.3 更新联系人信息

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

#### 3.4 屏蔽联系人

**接口**: `POST /api/v1/contacts/{conv_id}/block`

**请求头**: `Authorization: Bearer token`

#### 3.5 取消屏蔽联系人

**接口**: `POST /api/v1/contacts/{conv_id}/unblock`

**请求头**: `Authorization: Bearer token`

#### 3.6 删除联系人

**接口**: `DELETE /api/v1/contacts/{conv_id}`

**请求头**: `Authorization: Bearer token`

**说明**:

- 删除联系人关系
- 不删除聊天记录（客户端本地管理）

#### 3.7 获取对话信息

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

#### 3.8 获取历史消息

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

- message_type: 1=文本, 2=图片, 3=语音, 4=视频, 5=系统消息
- status: 1=已发送, 2=已送达, 3=已读, 4=失败

### 4. 联系人添加

#### 4.1 添加AI联系人

**接口**: `POST /api/v1/contacts/add`

**请求头**: `Authorization: Bearer token`

**请求参数**:

```json
{
  "contact_qiao_id": "qiao_xm001",
  "alias": "小萌",
  "tags": ["朋友", "聊天"],
  "source": "discovery"
}
```

**成功响应**:

```json
{
  "conv_id": "conv_xyz789",
  "im_conv_id": "system_conversation_id",
  "contact_qiao_id": "qiao_xm001",
  "contact_type": 2,
  "alias": "小萌",
  "tags": ["朋友", "聊天"],
  "profile": {
    "nickname": "小萌",
    "gender": 2,
    "avatar_url": "assets://avatar_01"
  }
}
```

**说明**:

- 只能添加AI联系人(contact_type=2)
- 验证联系人数量限制(默认1个,可通过订阅增加)
- 验证AI角色是否可用
- 系统自动填入初始备注(可由用户修改)
- source: 添加来源(discovery=发现页, search=搜索, recommend=推荐等)
- 直接创建联系人关系,无需审批

### 5. 联系人申请(2.0功能,暂不实现)

#### 5.1 发送联系人申请

**接口**: `POST /api/v1/contact-requests`

**请求头**: `Authorization: Bearer token`

**请求参数**:

```json
{
  "to_qiao_id": "qiao_xm001",
  "message": "你好，我想和你聊天",
  "alias": "小萌",
  "tags": ["朋友", "聊天"]
}
```

#### 5.2 获取联系人申请列表

**接口**: `GET /api/v1/contact-requests`

**请求头**: `Authorization: Bearer token`

**查询参数**: `?cursor=xxx&limit=20`

#### 5.3 接受联系人申请

**接口**: `POST /api/v1/contact-requests/{id}/accept`

**请求头**: `Authorization: Bearer token`

#### 5.4 拒绝联系人申请

**接口**: `POST /api/v1/contact-requests/{id}/reject`

**请求头**: `Authorization: Bearer token`

### 6. 发现页面

#### 6.1 获取广场随机联系人

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
      "name": "avatar_01",
      "category": 1,
      "url": "assets://avatar_01",
      "description": "默认头像1",
      "sort_order": 1
    }
  ]
}
```

**说明**:

- MVP阶段使用hardcode的默认头像
- 头像文件内置在小程序中
- avatar_url格式: assets://avatar_01, assets://avatar_02等
- 2.0功能: 管理后台可动态添加新头像

### 8. 系统配置

#### 8.1 获取IM配置 (2.0功能,暂不实现)

**接口**: `GET /api/v1/system/im-config`

**请求头**: `Authorization: Bearer token`

**成功响应**:

```json
{
  "provider": 1,
  "key": "..."
}
```

**说明**:

- 用于动态下发IM provider相关配置
- provider: 1=LeanCloud, 2=其他
- 当前版本不实现，contacts接口的im_conv_id已满足基本需求

### 9. Webhook

#### 9.1 接收LeanCloud消息推送

**接口**: `POST /api/v1/webhook/leancloud/{webhook_token}`

**说明**:

- webhook_token: 安全令牌，防止伪造请求
- 由LeanCloud服务器调用
- 处理消息接收、消息状态更新等事件
