# 对话接口（未来开发）

## 接口列表

- [获取对话信息](#获取对话信息) - `GET /api/v1/contacts/{conv_id}/conversation`
- [获取历史消息](#获取历史消息) (该接口废弃，不要进行开发) - `GET /api/v1/contacts/{conv_id}/messages`

---

## 获取对话信息

### 基本信息

- **路径**: `GET /api/v1/contacts/{conv_id}/conversation`
- **认证**: Bearer Token（必需）

### 路径参数

- `conv_id` (string, 必填) - 对话ID

### 成功响应 (200)

```json
{
  "conv_id": "conv_xyz789",
  "im_conv_id": "system_conversation_id",
  "contact_qiao_id": "qiao_xm001",
  "contact_info": {
    "nickname": "小萌",
    "avatar_url": "assets://8923",
    "gender": 2
  }
}
```

**字段说明**:

- `conv_id` (string) - 对话ID
- `im_conv_id` (string) - IM系统对话ID，用于初始化消息客户端连接
- `contact_qiao_id` (string) - 联系人的qiao_id
- `contact_info` (object) - 联系人信息
  - `nickname` (string) - 昵称
  - `avatar_url` (string) - 头像URL
  - `gender` (integer) - 性别，枚举值见：`backend/app/enums/common.py` - `Gender`

### 错误响应

**400 Bad Request**:

- `"操作异常"` - 对话不存在或无权访问

**500 Internal Server Error**:

- `"系统错误"` - 服务器内部错误

### 业务说明

- 此接口用于对话页面初始化，提供 `im_conv_id` 用于连接消息服务
- `im_conv_id` 来自系统注册表，前端需要使用系统接口保持同步

---

## 获取历史消息

### 基本信息

- **路径**: `GET /api/v1/contacts/{conv_id}/messages`
- **认证**: Bearer Token（必需）
- **分页**: 支持 cursor-based pagination

### 路径参数

- `conv_id` (string, 必填) - 对话ID

### 请求参数

**查询参数**:

- `cursor` (string, 可选) - 分页游标
- `limit` (integer, 可选) - 每页数量，默认50，最大100

### 成功响应 (200)

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
    "cursor": "next_cursor_value",
    "has_more": true
  }
}
```

**字段说明**:

- `msg_id` (string) - 消息ID
- `from_qiao_id` (string) - 发送者qiao_id
- `to_qiao_id` (string) - 接收者qiao_id
- `content` (string) - 消息内容
- `message_type` (integer) - 消息类型
  - `1` - TEXT（文本消息）
  - `2` - TYPING_START（开始输入）
  - `3` - TYPING_END（结束输入）
  - `4` - CHAT_INFO（聊天信息）
  - `9` - NOTIFICATION（通知消息）
- `sent_time` (integer) - 发送时间（Unix时间戳，毫秒）
- `status` (integer) - 消息状态
  - `1` - 已发送
  - `2` - 已送达
  - `3` - 已读
  - `4` - 失败

### 错误响应

**400 Bad Request**:

- `"操作异常"` - 对话不存在或无权访问

**500 Internal Server Error**:

- `"系统错误"` - 服务器内部错误

### 业务说明

- 返回历史消息记录
- 按时间倒序排列（最新的在前）
- 不包括输入状态消息（TYPING_START, TYPING_END）
- 客户端应该本地缓存消息，减少API调用
