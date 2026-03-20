# 联系人申请接口

## 接口列表

- [发送联系人申请](#发送联系人申请) - `POST /api/v1/contact-requests`
- [接受联系人申请](#接受联系人申请) - `POST /api/v1/contact-requests/{id}/accept`
- [忽略联系人申请](#忽略联系人申请) - `POST /api/v1/contact-requests/{id}/ignore`


---

## 数据流说明

**好友申请采用消息推送机制，不提供列表查询接口**：

1. **发送申请**：调用 `POST /api/v1/contact-requests` 接口
2. **接收申请**：通过 NOTIFICATION 消息推送（`message_type=9, notification_type=1`）
3. **客户端存储**：收到消息后存储到本地数据库（IndexedDB/SQLite）
4. **查看列表**：直接读取本地数据库
5. **处理申请**：调用接受/忽略接口

**NOTIFICATION 消息格式**：

```json
{
  "message_type": 9,
  "notification_type": 1,
  "content": {
    "request_id": "req_123",
    "from_qiao_id": "qiao_user001",
    "message": "你好，我想加你为好友",
    "from_profile": {
      "nickname": "小明",
      "avatar_url": "https://cdn.example.com/users/qiao_user001.webp",
      "gender": 1,
      "bio": "喜欢音乐"
    }
  }
}
```

---

## 发送联系人申请

### 基本信息

- **路径**: `POST /api/v1/contact-requests`
- **认证**: Bearer Token（必需）
- **速率限制**: 无

### 请求参数

```json
{
  "to_qiao_id": "qiao_xm001",
  "message": "你好，我想和你聊天",
  "category_key": "friend",
  "alias": "小萌",
  "tags": ["朋友", "聊天"],
  "source": 1
}
```

**字段说明**:

- `to_qiao_id` (string, 必填)
  - 目标联系人的 qiao_id
  - 必须存在于系统中

- `message` (string, 可选)
  - 申请消息
  - 最长 500 字符

- `category_key` (string, 可选)
  - 来源分类键（kebab-case）
  - 仅作为请求上下文持久化

- `alias` (string, 可选)
  - 备注
  - 显示宽度上限：24（约 12 个中文或 24 个英文）
  - 字符上限：32（按字符簇计数）

- `tags` (array, 可选)
  - 标签列表
  - 每个标签最长 20 字符

- `source` (integer, 可选)
  - 请求来源，默认 `1`
  - 枚举值定义见：`backend/app/enums/common.py` - `ContactRequestSource`

### 成功响应 (200)

```json
{
  "message": "请求已发送"
}
```

### 错误响应

**400 Bad Request**:

- `"已添加该联系人"` - 联系人关系已存在
- `"联系人数量已达上限"` - 联系人数量超限

**429 Too Many Requests**:

- `"请求过于频繁"` - 超过速率限制

**500 Internal Server Error**:

- `"系统错误（error_code）"` - 服务器内部错误

### 核心设计原则

1. **统一API设计**: 所有联系人使用同一个API，前端无需区分类型
2. **后端自动路由**: 后端内部判断目标类型并路由到相应处理逻辑
3. **统一返回格式**: 所有请求都返回"请求已发送"，不暴露内部处理细节
4. **防重复请求**: 相同的请求在有效期内只能有一条

### 业务流程说明

**前端视角**:

1. 用户在发现页面或搜索结果中点击"添加"
2. 调用本接口发送申请
3. 收到"请求已发送"响应
4. 等待对方接受（或系统自动处理）

**后端内部流程**（前端无需关心）:

1. 验证联系人关系（是否已添加、数量上限）
2. 如果联系人已删除（`is_deleted=1`），恢复联系人关系
3. 创建联系人请求记录（`contact_requests` 表，持久化 `category_key`、`alias`、`tags`）
4. 根据目标类型执行相应逻辑
5. 发送 NOTIFICATION 消息给接收方
6. 返回统一响应

**联系人恢复逻辑**:

- 如果之前删除过该联系人，再次添加时会恢复联系人关系
- 使用新的 `alias` 和 `tags`，不保留旧的 `remark`
- 保留原有的 `conversation_id`
- 同样返回"请求已发送"

---

## 接受联系人申请

### 基本信息

- **路径**: `POST /api/v1/contact-requests/{id}/accept`
- **认证**: Bearer Token（必需）
- **说明**: 接受后会创建联系人关系

### 路径参数

- `id` (string, 必填) - 申请记录ID（从 NOTIFICATION 消息中获取的 `request_id`）

### 请求参数

```json
{
  "alias": "小明",
  "tags": ["同事"]
}
```

**字段说明**:

- `alias` (string, 可选)
  - 备注
  - 显示宽度上限：24（约12个中文或24个英文）
  - 字符上限：32（按字符簇计数）

- `tags` (array, 可选)
  - 标签列表
  - 每个标签最长20字符

### 成功响应 (200)

```json
{
  "conversation_id": "conv_xyz789",
  "contact_qiao_id": "qiao_user001",
  "alias": "小明",
  "tags": ["同事"],
  "remark": null,
  "is_pinned": false,
  "is_muted": false,
  "is_blocked": false,
  "profile": {
    "nickname": "小明",
    "avatar_url": "https://cdn.example.com/users/qiao_user001.webp",
    "gender": 1,
    "bio": "喜欢音乐"
  }
}
```

**字段说明**:

- `conversation_id` (string) - 对话ID，用于标识联系人关系
- `contact_qiao_id` (string) - 联系人的qiao_id
- `alias` (string) - 备注
- `tags` (array) - 标签列表
- `remark` (string) - 描述
- `is_pinned` (boolean) - 是否置顶
- `is_muted` (boolean) - 是否免打扰
- `is_blocked` (boolean) - 是否屏蔽
- `profile` (object) - 联系人资料信息
  - `nickname` (string) - 昵称
  - `avatar_url` (string) - 动态生成的头像 CDN URL
  - `gender` (integer) - 性别，枚举值见：`backend/app/enums/common.py` - `Gender`
  - `bio` (string) - 个性签名

### 错误响应

**400 Bad Request**:

- `"操作异常"` - 申请不存在或已处理

**500 Internal Server Error**:

- `"系统错误（error_code）"` - 服务器内部错误

### 业务说明

**接受后的操作**:

1. 创建联系人记录（`contact` 表）
2. 更新申请状态为"已接受"
3. 发送通知消息给申请人（系统自动处理）
4. 返回完整的联系人信息

**关于通知**:

- 系统会自动发送通知消息给申请人
- 前端无需手动发送通知
- 申请人会在消息列表中看到通知

---

## 忽略联系人申请

### 基本信息

- **路径**: `POST /api/v1/contact-requests/{id}/ignore`
- **认证**: Bearer Token（必需）
- **说明**: 忽略后不会创建联系人关系，也不会通知申请人

### 路径参数

- `id` (string, 必填) - 申请记录ID（从 NOTIFICATION 消息中获取的 `request_id`）

### 请求参数

无需请求体

### 成功响应 (200)

```json
{
  "message": "已忽略"
}
```

### 错误响应

**400 Bad Request**:

- `"操作异常"` - 申请不存在或已处理

**500 Internal Server Error**:

- `"系统错误（error_code）"` - 服务器内部错误

### 业务说明

**忽略后的操作**:

1. 更新申请状态为"IGNORED"
2. 不发送通知给申请人（保护隐私）
3. 申请人无法得知被忽略

**隐私保护**:

- 忽略操作不会通知申请人
- 这样可以避免尴尬和冲突
