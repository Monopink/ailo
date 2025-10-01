# API接口设计文档

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

## 管理后台API设计

### 架构原则重申

管理后台遵循**API优先设计**和**混合编程范式**，明确区分功能职责：

#### ✅ **使用Starlette ModelView的功能**

- **基础数据CRUD**: 用户、AI配置、LLM配置、系统配置等
- **简单查询和编辑**: 直接操作数据表的功能
- **标准管理界面**: 列表、创建、编辑、删除操作

#### 🚀 **使用专门API的功能**

- **复杂业务逻辑**: AI对话测试、分数计算、提示词合成
- **外部服务调用**: LLM服务测试、第三方API调用
- **数据聚合分析**: 仪表板统计、性能监控
- **批量操作**: 需要事务处理的复杂操作

### 认证方式

管理后台API使用Session-based认证，与Starlette-Admin共享认证状态。

**请求头：**

```
Cookie: session=admin_session_value
```

### 通用响应格式

#### 成功响应

```json
{
  "success": true,
  "data": {
    // 具体数据
  },
  "message": "操作成功"
}
```

#### 错误响应

```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "错误信息",
    "details": {}
  }
}
```

### 1. 仪表板API

#### 1.1 获取仪表板统计数据

```
GET /admin-api/dashboard/stats
```

**功能**: 实时系统统计数据聚合

**响应：**

```json
{
  "success": true,
  "data": {
    "total_users": 1250,
    "total_ai_characters": 45,
    "total_messages": 15680,
    "active_sessions": 23,
    "today_new_users": 12,
    "today_messages": 456,
    "system_status": "healthy"
  }
}
```

### 2. AI测试管理API

#### 2.1 AI角色对话测试

```http
POST /admin-api/ai/test-chat
```

**功能**: 完整的AI对话流程测试，包含11步对话处理流程

**请求参数：**

```json
{
  "character_qiao_id": "qiao_ai001",
  "user_qiao_id": "qiao_test001",
  "llm_config_key": "doubao_primary",
  "test_message": "你好，今天天气怎么样？",
  "enable_thinking": true,
  "test_session_id": "optional_session_id"
}
```

**响应：**

```json
{
  "success": true,
  "data": {
    "test_session_id": "test_uuid_123",
    "request_id": "req_snowflake_id",
    "conversation_result": {
      "ai_response": "今天天气很不错呢！阳光明媚，很适合出去走走。",
      "thinking_process": "用户询问天气，我应该给出积极正面的回应...",
      "score_updates": {
        "friend": 520,
        "romance": 180
      },
      "memory_operations": [],
      "should_reply": true,
      "attack_detected": false
    },
    "performance": {
      "response_time_ms": 1250,
      "token_usage": {
        "prompt_tokens": 156,
        "completion_tokens": 45,
        "total_tokens": 201
      }
    },
    "config_used": {
      "config_key": "doubao_primary",
      "provider_name": "doubao",
      "model": "doubao-pro-4k"
    }
  }
}
```

#### 2.2 分数算法测试

```http
POST /admin-api/ai/test-algorithm
```

**功能**: 测试分数偏移算法，支持单次和批量测试

**请求参数：**

```json
{
  "algorithm": 2,
  "score": 600,
  "initial_position": 500,
  "params": {
    "strength": 0.7
  },
  "batch_test": {
    "enabled": false,
    "score_range": [0, 1000],
    "step": 50
  }
}
```

**响应：**

```json
{
  "success": true,
  "data": {
    "single_result": {
      "new_score": 567.8,
      "offset": 67.8,
      "algorithm_name": "V1 Non-linear Offset"
    },
    "calculation_details": {
      "direction": 100,
      "normalized_direction": 0.2,
      "curve_factor": 1.7,
      "curved_offset": 67.8
    },
    "batch_results": null
  }
}
```

#### 2.3 提示词预览测试

```http
POST /admin-api/ai/test-prompt
```

**功能**: 提示词合成和预览，用于调试提示词模板

**请求参数：**

```json
{
  "character_qiao_id": "qiao_ai001",
  "user_qiao_id": "qiao_test001",
  "relationship_override": {
    "relationship_id": 1,
    "scores": {"friend": 600, "romance": 200}
  },
  "context_length": 10,
  "include_thinking": true
}
```

**响应：**

```json
{
  "success": true,
  "data": {
    "prompt_preview": {
      "system_prompt": "你是一个AI角色...",
      "user_context": "最近的对话历史...",
      "thinking_prompt": "请分析用户的意图...",
      "full_prompt": "完整的合成提示词"
    },
    "placeholder_info": {
      "total_placeholders": 15,
      "replaced_count": 15,
      "missing_placeholders": []
    },
    "character_info": {
      "qiao_id": "qiao_ai001",
      "name": "小萌",
      "current_relationship": "普通朋友"
    }
  }
}
```

### 3. LLM测试管理API

#### 3.1 LLM配置测试

```http
POST /admin-api/llm/test
```

**功能**: 测试LLM配置和性能，支持多配置并行测试

**请求参数：**

```json
{
  "config_keys": ["doubao_primary"],
  "test_cases": [
    {
      "name": "基础对话测试",
      "prompt": "请介绍一下人工智能的发展历史",
      "temperature": 0.7,
      "max_tokens": 500,
      "expected_type": "string"
    },
    {
      "name": "结构化输出测试",
      "prompt": "分析这段文字的情感",
      "json_schema": {
        "type": "object",
        "properties": {
          "response": {"type": "string"},
          "confidence": {"type": "number", "minimum": 0, "maximum": 1}
        },
        "required": ["response", "confidence"]
      },
      "expected_type": "json"
    }
  ],
  "performance_test": {
    "enabled": false,
    "concurrent_requests": 3,
    "iterations": 10
  }
}
```

**响应：**

```json
{
  "success": true,
  "data": {
    "test_results": [
      {
        "config_key": "doubao_primary",
        "test_cases": [
          {
            "name": "基础对话测试",
            "success": true,
            "response": "人工智能的发展可以追溯到20世纪50年代...",
            "response_time_ms": 890,
            "token_usage": {
              "prompt_tokens": 25,
              "completion_tokens": 120,
              "total_tokens": 145
            }
          }
        ],
        "performance_metrics": {
          "avg_response_time": 890,
          "success_rate": 1.0,
          "total_tokens": 145
        }
      }
    ],
    "test_metadata": {
      "timestamp": 1710001111,
      "test_id": "test_uuid_456"
    }
  }
}
```

### 4. 后续开发功能 (暂不实施)

以下功能作为后续开发方向，当前阶段不进行详细设计和实施：

#### 4.1 系统监控API (TODO)

- **性能监控**: `/admin-api/system/performance` - 系统性能指标
- **健康检查**: `/admin-api/system/health` - 服务可用性检查
- **日志分析**: `/admin-api/system/logs` - 系统日志聚合分析

#### 4.2 批量操作API (TODO)

- **批量AI测试**: `/admin-api/batch/ai-test` - 多角色并行测试
- **批量配置更新**: `/admin-api/batch/config-update` - 批量配置管理
- **数据导入导出**: `/admin-api/batch/data-export` - 数据批量处理

#### 4.3 高级分析API (TODO)

- **对话质量分析**: `/admin-api/analytics/conversation-quality` - AI对话质量评估
- **用户行为分析**: `/admin-api/analytics/user-behavior` - 用户使用模式分析
- **性能趋势分析**: `/admin-api/analytics/performance-trends` - 系统性能趋势

**注意**: 这些功能将在核心功能稳定后逐步实施，当前专注于AI测试和LLM测试的核心功能。

### 管理后台专用错误码

- `ADMIN_UNAUTHORIZED`: 管理员未登录
- `ADMIN_FORBIDDEN`: 管理员权限不足
- `AI_CHARACTER_NOT_FOUND`: AI角色不存在
- `LLM_CONFIG_NOT_FOUND`: LLM配置不存在
- `TEST_USER_NOT_FOUND`: 测试用户不存在
- `ALGORITHM_VALIDATION_FAILED`: 算法参数验证失败
- `LLM_REQUEST_FAILED`: LLM请求失败
- `CONFIG_UPDATE_FAILED`: 配置更新失败

## 安全考虑

1. **API限流**：防止恶意请求
2. **参数验证**：严格验证所有输入参数
3. **SQL注入防护**：使用参数化查询
4. **XSS防护**：输出内容转义
5. **CSRF防护**：使用CSRF Token
6. **敏感信息脱敏**：日志中不记录敏感信息
7. **管理后台访问控制**：基于角色的权限管理
8. **操作日志记录**：记录所有管理操作
