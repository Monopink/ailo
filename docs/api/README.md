# API 接口文档

## 快速导航

### 认证相关

- [用户认证](auth.md) - 登录、注册、Token管理
- [账户安全](account-security.md) - 密码、邮箱、手机号管理

### 用户相关

- [用户资料](user.md) - 资料查询和更新、用户设置

### 联系人相关

- [联系人管理](contacts.md) - 联系人列表、详情、更新、删除
- [联系人申请](contact-requests.md) - 发送申请、接受、忽略

### 发现相关

- [发现页面](discovery.md) - 广场推荐、陌生人详情

### 媒体相关

- [媒体文件](media.md) - 文件上传、头像管理

### 系统相关

- [系统配置](system.md) - 系统级配置接口
- [LC-IM](leancloud-message.md) - LeanCloud 专用 IM 接口
- [离线消息](messages-offline.md) - 离线消息与ACK

---

## 通用规范

### 设计原则

- RESTful API设计风格
- 统一的响应格式
- 外部标识符使用qiao_id，内部使用Snowflake ID
- 所有时间字段使用Unix时间戳（毫秒）
- 分页使用cursor-based pagination
- 错误信息对用户友好，不暴露内部实现
- 业务抽象优先：API路径使用业务语义，不暴露技术实现细节
- 数据脱敏：敏感信息（如手机号）需要脱敏处理
- 不绑定具体前端逻辑，不在接口里堆业务
- 事件化、枚举化，而不是“随便传 JSON”

### 拟人化设计铁律

**本项目是AI拟人陪聊应用，核心目标是让用户相信这是真人交互。**

1. **避免暴露AI**：接口中不应该出现 "contact_type" 这些区分真人和AI的字段, 这些字段仅服务于后端
2. **隐藏技术细节**：与前端无关的后台逻辑, 例如 ai_types_id 等不应出现在API中
3. **尽量隐藏第三方**：API路径中尽量不包含第三方服务名称（如LeanCloud、Aliyun等）

### 认证方式

所有需要认证的API使用Bearer Token：

```http
Authorization: Bearer <token>
```

### 响应格式

**成功响应 (HTTP 200)**:

直接返回业务数据，无包装：

```json
{
  "qiao_id": "qiao_abc123",
  "nickname": "小明",
  "avatar_url": "https://cdn.example.com/profiles/qiao_abc123.webp"
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

**错误响应 (HTTP 4xx/5xx)**:

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
- 注：这是MVP阶段的简化设计，2.0版本将实现统一包装格式

### 错误处理原则

- 所有 API 都要有完善的错误处理
- 错误信息不能暴露内部实现细节
- 使用统一的错误响应格式
- **对于非预期的操作错误（如访问不存在的资源），不要暴露详细信息**
  - ❌ 错误示例：`"联系人不存在"`, `"对话不存在"`, `"用户不存在"`
  - ✅ 正确示例：`"操作异常"`, 或不返回任何提示信息（直接返回空数据）
  - 原因：避免信息泄露，防止恶意用户通过错误消息探测系统状态

### 枚举值管理原则

**单一数据源**：

- 所有枚举值定义在 `backend/app/enums/common.py` 中
- 数据库文档（`docs/database/*.md`）作为枚举值的参考说明
- API 文档不硬编码枚举值，统一引用 `backend/app/enums/common.py`

### 速率限制

**短信验证码**:

- 速率限制：1次/60秒（同一号码）
- 白名单：支持配置白名单号码（不受限制）

**用户认证**:

- 速率限制：10次/小时
- 失败次数限制：5次失败后锁定
- 锁定时长：15分钟
- 人机验证触发：3次失败后需要人机验证

**消息发送**:

- 短期限制：5条/10秒
- 长期限制：20条/分钟

**通用API**:

- 通用限制：100次请求/分钟/IP
- 白名单：支持配置白名单IP（不受限制）
