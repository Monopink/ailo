# 联系人申请接口

## 接口列表

- [发送联系人申请](#发送联系人申请) - `POST /api/v1/contact-requests`
- [接受联系人申请](#接受联系人申请) - `POST /api/v1/contact-requests/{request_id}/accept`
- [忽略联系人申请](#忽略联系人申请) - `POST /api/v1/contact-requests/{request_id}/ignore`

## 相关文档

联系人申请的流程与规则见：

- `docs/spec/contact/request-flow.md`
- `docs/spec/contact/ai-creation.md`
- `docs/spec/contact/management.md`

---

## 发送联系人申请

### 基本信息

- **路径**: `POST /api/v1/contact-requests`
- **认证**: Bearer Token（必需）
- **业务速率限制**: 无
- **全局IP限流**: `/api/v1/*` 受全局限流中间件保护，可能返回 `429`（含 `Retry-After` 响应头）

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
  - 持久化到 `contact_requests.tags`
  - `[]` 表示显式写入空标签
  - 校验规则与联系人标签一致，见：`docs/api/contacts.md` - 更新联系人信息 - `tags`

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
- `"请求参数错误"` - 请求参数校验失败

**429 Too Many Requests**（全局IP限流）:

- `"请求过于频繁，请稍后再试"` - 超过速率限制

**500 Internal Server Error**:

- `"系统错误（error_code）"` - 服务器内部错误

---

## 接受联系人申请

### 基本信息

- **路径**: `POST /api/v1/contact-requests/{request_id}/accept`
- **认证**: Bearer Token（必需）
- **说明**: 接受后会创建联系人关系

### 路径参数

- `request_id` (string, 必填) - 申请记录ID（`contact_requests.id`，Snowflake bigint，使用字符串传输避免 JS 精度丢失）

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
  - 校验规则与联系人标签一致，见：`docs/api/contacts.md` - 更新联系人信息 - `tags`

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

---

## 忽略联系人申请

### 基本信息

- **路径**: `POST /api/v1/contact-requests/{request_id}/ignore`
- **认证**: Bearer Token（必需）
- **说明**: 忽略后不会创建联系人关系，也不会通知申请人

### 路径参数

- `request_id` (string, 必填) - 申请记录ID（`contact_requests.id`，Snowflake bigint，使用字符串传输避免 JS 精度丢失）

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
