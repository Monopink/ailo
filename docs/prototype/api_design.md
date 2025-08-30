wo# API接口设计文档

## 设计原则

- 使用RESTful API设计风格
- 统一的响应格式
- 外部标识符使用qiao_id，内部使用Snowflake ID
- 所有时间字段使用Unix时间戳
- 分页使用cursor-based pagination
- 错误信息对用户友好，不暴露内部实现

## 重要设计理念

**本项目是AI拟人陪聊应用，核心目标是让用户相信这是真人交互。**

### 铁律：拟人化设计

1. **避免AI相关字眼**：在所有用户界面、API响应、提示信息中避免使用"AI"、"机器人"、"助手"等字眼
2. **一视同仁原则**：在设计和交互中将用户和AI角色一视同仁，使用统一的称谓如"联系人"、"好友"等
3. **真人化体验**：所有交互设计都要营造真人聊天的感觉，包括响应时间、语言风格、行为模式等
4. **隐藏技术细节**：对用户隐藏所有技术实现细节，如模型调用、上下文管理等

## 通用响应格式

### 成功响应

```json
{
  "success": true,
  "data": {
    // 具体数据
  },
  "message": "操作成功"
}
```

### 错误响应

```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "用户友好的错误信息"
  }
}
```

### 分页响应

```json
{
  "success": true,
  "data": {
    "items": [],
    "pagination": {
      "cursor": "next_cursor_value",
      "has_more": true,
      "total": 100
    }
  }
}
```

## 小程序端API

### 1. 用户认证

#### 1.1 发送验证码

```
POST /api/v1/auth/send-sms
```

**请求参数：**

```json
{
  "phone": "13800138000"
}
```

**响应：**

```json
{
  "success": true,
  "data": {
    "expires_in": 300
  },
  "message": "验证码已发送"
}
```

#### 1.2 用户注册（自动登录）

```
POST /api/v1/auth/register
```

**请求参数：**

```json
{
  "phone": "13800138000",
  "sms_code": "123456",
  "nickname": "小雨",
  "gender": 2,
  "avatar_url": "avatar_url_or_null"
}
```

**响应：**

```json
{
  "success": true,
  "data": {
    "user": {
      "qiao_id": "qiao_abc123",
      "username": "qiao_abc123",
      "phone": "13800138000"
    },
    "profile": {
      "nickname": "小雨",
      "gender": 2,
      "avatar_url": "avatar_url"
    },
    "session": {
      "token": "session_token",
      "expires_at": 1710001111
    }
  },
  "message": "注册成功"
}
```

#### 1.3 用户登录（验证码）

```
POST /api/v1/auth/login/sms
```

**请求参数：**

```json
{
  "phone": "13800138000",
  "sms_code": "123456",
  "device_type": 4,
  "device_id": "device_unique_id"
}
```

#### 1.4 用户登录（密码）

```
POST /api/v1/auth/login/password
```

**请求参数：**

```json
{
  "username": "qiao_abc123",
  "password": "user_password",
  "device_type": 4,
  "device_id": "device_unique_id"
}
```

**登录响应格式：**

```json
{
  "success": true,
  "data": {
    "user": {
      "qiao_id": "qiao_abc123",
      "username": "qiao_abc123",
      "phone": "13800138000"
    },
    "profile": {
      "nickname": "小雨",
      "gender": 2,
      "avatar_url": "avatar_url"
    },
    "session": {
      "token": "session_token",
      "expires_at": 1710001111
    }
  },
  "message": "登录成功"
}
```

#### 1.5 退出登录

```
POST /api/v1/auth/logout
```

**请求头：**

```
Authorization: Bearer session_token
```

### 2. 用户资料管理

#### 2.1 获取用户资料

```
GET /api/v1/user/profile
```

**请求头：**

```
Authorization: Bearer session_token
```

**响应：**

```json
{
  "success": true,
  "data": {
    "user": {
      "qiao_id": "qiao_abc123",
      "username": "qiao_abc123",
      "phone": "13800138000",
      "created_at": 1710001111
    },
    "profile": {
      "nickname": "小雨",
      "gender": 2,
      "avatar_url": "avatar_url",
      "bio": "喜欢看书和旅行",
      "region": "北京",
      "tags": ["文艺", "旅行"]
    }
  }
}
```

#### 2.2 更新用户资料

```
PUT /api/v1/user/profile
```

**请求参数：**

```json
{
  "nickname": "新昵称",
  "gender": 2,
  "avatar_url": "new_avatar_url",
  "bio": "新的个人简介",
  "region": "上海"
}
```

### 3. 广场功能

#### 3.1 获取广场联系人列表

```
GET /api/v1/square/contacts
```

**请求参数：**

```
?category=1&cursor=cursor_value&limit=20
```

**响应：**

```json
{
  "success": true,
  "data": {
    "items": [
      {
        "qiao_id": "qiao_xm001",
        "category": 1,
        "nickname": "小萌",
        "gender": 2,
        "avatar_url": "avatar_url",
        "bio": "喜欢音乐和电影，寻找有趣的聊天伙伴",
        "tags": ["音乐", "电影", "有趣"],
        "region": "上海"
      }
    ],
    "pagination": {
      "cursor": "next_cursor",
      "has_more": true
    }
  }
}
```

#### 3.2 发送联系人申请

```
POST /api/v1/contact-requests
```

**请求参数：**

```json
{
  "to_qiao_id": "qiao_xm001",
  "message": "你好，我想和你聊天",
  "alias": "小萌",
  "tags": ["朋友", "聊天"]
}
```

**响应：**

```json
{
  "success": true,
  "message": "联系人申请已发送"
}
```

### 4. 联系人管理

#### 4.1 获取联系人列表（用于聊天列表）

```
GET /api/v1/contacts
```

**请求参数：**

```
?cursor=cursor_value&limit=20
```

**说明：** 返回聊天列表所需的基本信息，包含联系人的基础资料。

**响应：**

```json
{
  "success": true,
  "data": {
    "items": [
      {
        "conv_id": "conv_xyz789",
        "contact_qiao_id": "qiao_xm001",
        "contact_type": 2,
        "alias": "小萌",
        "avatar_alias_url": null,
        "tags": ["朋友", "聊天"],
        "remark": "很有趣的聊天伙伴",
        "is_pinned": 0,
        "is_muted": 0,
        "profile": {
          "nickname": "小萌",
          "gender": 2,
          "avatar_url": "avatar_url",
          "bio": "喜欢音乐和电影，寻找有趣的聊天伙伴",
          "region": "上海"
        },
        "created_at": 1710001111,
        "updated_at": 1710001111
      }
    ],
    "pagination": {
      "cursor": "next_cursor",
      "has_more": true
    }
  }
}
```

#### 4.2 获取单个联系人详情

```
GET /api/v1/contacts/{conv_id}
```

**说明：** 获取单个联系人的完整信息，用于联系人详情页面。

**响应：**

```json
{
  "success": true,
  "data": {
    "contact": {
      "conv_id": "conv_xyz789",
      "contact_qiao_id": "qiao_xm001",
      "contact_type": 2,
      "alias": "小萌",
      "avatar_alias_url": null,
      "tags": ["朋友", "聊天"],
      "remark": "很有趣的聊天伙伴",
      "is_pinned": 0,
      "is_muted": 0,
      "is_blocked": 0,
      "profile": {
        "nickname": "小萌",
        "gender": 2,
        "avatar_url": "avatar_url",
        "bio": "喜欢音乐和电影，寻找有趣的聊天伙伴",
        "region": "上海"
      },
      "created_at": 1710001111,
      "updated_at": 1710001111
    }
  }
}
```

#### 4.3 更新联系人信息

```
PUT /api/v1/contacts/{conv_id}
```

**请求参数：**

```json
{
  "alias": "新的备注名",
  "avatar_alias_url": "new_avatar_url",
  "tags": ["新标签1", "新标签2"],
  "remark": "新的备注信息",
  "is_pinned": 1,
  "is_muted": 0
}
```

#### 4.4 删除联系人

```
DELETE /api/v1/contacts/{conv_id}
```

### 5. 媒体文件管理

#### 5.1 文件上传

```
POST /api/v1/media/upload
```

**请求参数（multipart/form-data）：**

```
file: 文件内容
file_type: 1 (1=avatar, 2=emoji, 3=image, 4=document)
```

**响应：**

```json
{
  "success": true,
  "data": {
    "file": {
      "file_id": "file_abc123",
      "file_url": "https://example.com/files/abc123.jpg",
      "file_type": 1,
      "file_size": 102400,
      "mime_type": "image/jpeg"
    }
  },
  "message": "文件上传成功"
}
```

#### 5.2 获取表情列表

```
GET /api/v1/emoticons
```

**请求参数：**

```
?category=1&limit=50
```

**响应：**

```json
{
  "success": true,
  "data": {
    "items": [
      {
        "code": "smile",
        "category": 1,
        "url": "emoji_url",
        "description": "微笑表情",
        "sort_order": 1
      }
    ]
  }
}
```

### 7. LeanCloud Webhook

LeanCloud消息Webhook的格式由LeanCloud官方规定，具体实现时参考LeanCloud文档。

**处理流程：**

1. 验证消息签名
2. 解析消息内容
3. 进行安全检测
4. 如果是发给角色的消息，调用处理逻辑
5. 记录到message_history表
6. 返回响应给LeanCloud

## 管理后台API

### 认证方式

管理后台使用独立的认证系统，基于admin_users表。

#### 管理员登录

```http
POST /api/v1/admin/auth/login
```

**请求参数：**

```json
{
  "username": "admin_user",
  "password": "admin_password"
}
```

**响应：**

```json
{
  "success": true,
  "data": {
    "admin": {
      "id": 123,
      "username": "admin_user",
      "role": 1
    },
    "token": "admin_jwt_token",
    "expires_at": 1710001111
  }
}
```

### 1. 用户管理

#### 1.1 获取用户列表

```http
GET /api/v1/admin/users
```

**请求参数：**

```
?status=1&search=keyword&cursor=cursor_value&limit=20
```

**响应：**

```json
{
  "success": true,
  "data": {
    "items": [
      {
        "id": 123,
        "qiao_id": "qiao_abc123",
        "username": "qiao_abc123",
        "phone": "13800138000",
        "status": 1,
        "user_type": 1,
        "last_login": 1710001111,
        "profile": {
          "nickname": "用户昵称",
          "gender": 1,
          "avatar_url": "avatar_url"
        },
        "created_at": 1710001111,
        "updated_at": 1710001111
      }
    ],
    "pagination": {
      "cursor": "next_cursor",
      "has_more": true,
      "total": 1000
    }
  }
}
```

#### 1.2 获取用户详情

```http
GET /api/v1/admin/users/{user_id}
```

#### 1.3 更新用户状态

```http
PUT /api/v1/admin/users/{user_id}/status
```

**请求参数：**

```json
{
  "status": 2,
  "reason": "违规操作"
}
```

### 2. AI管理

#### 2.1 获取AI角色列表

```http
GET /api/v1/admin/ai/characters
```

#### 2.2 获取AI人格列表

```http
GET /api/v1/admin/ai/personalities
```

#### 2.3 创建AI人格

```http
POST /api/v1/admin/ai/personalities
```

**请求参数：**

```json
{
  "name": "人格名称",
  "prompt": "人格提示词模板",
  "json_schema": {},
  "placeholders": [
    {
      "placeholder_key": "name",
      "display_name": "姓名",
      "description": "AI角色的姓名",
      "example_value": "小助手",
      "is_required": 1
    }
  ]
}
```

### 3. 消息管理

#### 3.1 获取消息历史

```http
GET /api/v1/admin/messages
```

**请求参数：**

```
?conversation_id=conv_123&from_type=1&start_time=1710001111&end_time=1710002222&cursor=cursor_value&limit=50
```

#### 3.2 获取投递失败消息

```http
GET /api/v1/admin/messages/failures
```

#### 3.3 重试失败消息

```http
POST /api/v1/admin/messages/failures/{failure_id}/retry
```

### 4. 安全监控

#### 4.1 获取违规记录

```http
GET /api/v1/admin/security/violations
```

**请求参数：**

```
?user_id=123&violation_type=1&severity_level=3&status=1&cursor=cursor_value&limit=20
```

**响应：**

```json
{
  "success": true,
  "data": {
    "items": [
      {
        "id": 456,
        "user_qiao_id": "qiao_abc123",
        "violation_type": 1,
        "severity_level": 3,
        "original_message": "用户原始消息",
        "ai_detection_result": {
          "confidence": 0.95,
          "reason": "检测到提示词注入"
        },
        "auto_action_taken": 2,
        "manual_review_status": 1,
        "created_at": 1710001111
      }
    ],
    "pagination": {
      "cursor": "next_cursor",
      "has_more": true
    }
  }
}
```

#### 4.2 人工审核违规记录

```http
PUT /api/v1/admin/security/violations/{violation_id}/review
```

**请求参数：**

```json
{
  "manual_review_status": 2,
  "review_notes": "确认为误报"
}
```

### 5. 统计数据

#### 5.1 获取仪表盘数据

```http
GET /api/v1/admin/dashboard/stats
```

**响应：**

```json
{
  "success": true,
  "data": {
    "user_stats": {
      "total_users": 10000,
      "new_users_today": 50,
      "active_users_today": 1200,
      "active_users_week": 5000,
      "active_users_month": 8000
    },
    "message_stats": {
      "total_messages": 500000,
      "messages_today": 2000,
      "avg_messages_per_user": 50
    },
    "ai_stats": {
      "total_ai_requests": 100000,
      "ai_requests_today": 800,
      "active_ai_templates": 25
    },
    "security_stats": {
      "violations_today": 5,
      "high_risk_users": 3,
      "pending_reviews": 10
    }
  }
}
```

#### 5.2 获取用户统计趋势

```http
GET /api/v1/admin/stats/users
```

**请求参数：**

```
?period=daily&start_date=2024-01-01&end_date=2024-01-31
```

**响应：**

```json
{
  "success": true,
  "data": {
    "items": [
      {
        "stat_date": "2024-01-01",
        "total_users": 9950,
        "new_users": 45,
        "active_users": 1180
      }
    ]
  }
}
```

### 6. 系统管理

#### 6.1 获取系统配置

```http
GET /api/v1/admin/system/config
```

#### 6.2 更新系统配置

```http
PUT /api/v1/admin/system/config/{config_key}
```

**请求参数：**

```json
{
  "config_value": "new_value",
  "description": "配置描述"
}
```

#### 6.3 获取管理员列表（仅super_admin）

```http
GET /api/v1/admin/system/admins
```

#### 6.4 获取操作日志

```http
GET /api/v1/admin/system/operation-logs
```

**请求参数：**

```
?admin_user_id=123&operation_type=1&start_time=1710001111&end_time=1710002222&cursor=cursor_value&limit=50
```

## 错误码定义

### 通用错误码

- `INVALID_REQUEST`: 请求参数错误
- `UNAUTHORIZED`: 未授权访问
- `FORBIDDEN`: 权限不足
- `NOT_FOUND`: 资源不存在
- `RATE_LIMIT_EXCEEDED`: 请求频率超限

### 业务错误码

- `USER_NOT_FOUND`: 用户不存在
- `INVALID_SMS_CODE`: 验证码错误
- `PHONE_ALREADY_EXISTS`: 手机号已存在
- `CONTACT_ALREADY_EXISTS`: 联系人已存在
- `FILE_TOO_LARGE`: 文件过大
- `UNSUPPORTED_FILE_TYPE`: 不支持的文件类型

### 安全错误码

- `CONTENT_VIOLATION`: 内容违规
- `ACCOUNT_SUSPENDED`: 账户已停用
- `TOO_MANY_VIOLATIONS`: 违规次数过多

## 认证和授权

### 小程序端认证

- 使用Bearer Token认证
- Token存储在user_sessions表中
- 支持多设备登录，每种设备类型限制一个活跃会话

### 管理后台认证

- 使用JWT Token认证
- 基于admin_users表的角色权限控制
- super_admin > admin > viewer 三级权限

## 安全考虑

1. **API限流**：防止恶意请求
2. **参数验证**：严格验证所有输入参数
3. **SQL注入防护**：使用参数化查询
4. **XSS防护**：输出内容转义
5. **CSRF防护**：使用CSRF Token
6. **敏感信息脱敏**：日志中不记录敏感信息
