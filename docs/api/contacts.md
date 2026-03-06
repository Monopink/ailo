# 联系人管理接口

## 接口列表

- [获取联系人列表](#获取联系人列表) - `GET /api/v1/contacts`
- [获取单个联系人详情](#获取单个联系人详情) - `GET /api/v1/contacts/{conversation_id}`
- [更新联系人信息](#更新联系人信息) - `PUT /api/v1/contacts/{conversation_id}`
- [屏蔽联系人](#屏蔽联系人) - `POST /api/v1/contacts/{conversation_id}/block`
- [取消屏蔽联系人](#取消屏蔽联系人) - `POST /api/v1/contacts/{conversation_id}/unblock`
- [删除联系人](#删除联系人) - `DELETE /api/v1/contacts/{conversation_id}`

---

## 获取联系人列表

### 基本信息

- **路径**: `GET /api/v1/contacts`
- **认证**: Bearer Token（必需）
- **分页**: 支持 cursor-based pagination

### 请求参数

**查询参数**:

- `cursor` (string, 可选) - 分页游标
- `limit` (integer, 可选) - 每页数量，默认20，最大100

### 成功响应 (200)

```json
{
  "items": [
    {
      "conversation_id": "conv_xyz789",
      "contact_qiao_id": "qiao_xm001",
      "alias": "小萌",
      "tags": ["朋友"],
      "is_pinned": false,
      "is_muted": false,
      "is_blocked": false,
      "profile": {
        "nickname": "小萌",
        "avatar_url": "https://cdn.example.com/personas/qiao_xm001.webp",
        "gender": 2,
        "bio": "喜欢音乐和电影",
        "region": "上海"
      }
    }
  ],
  "pagination": {
    "cursor": "bmV4dF8yMA",
    "has_more": true
  }
}
```

**字段说明**:

- `conversation_id` (string) - 对话ID，用于标识联系人关系
- `contact_qiao_id` (string) - 联系人的qiao_id
- `alias` (string) - 备注
- `tags` (array) - 标签列表
- `last_message_time` (number|string|null) - 最近消息时间（毫秒时间戳或 ISO 时间字符串）
- `is_pinned` (boolean) - 是否置顶
- `is_muted` (boolean) - 是否免打扰
- `is_blocked` (boolean) - 是否已屏蔽
- `profile` (object) - 联系人资料信息
  - `nickname` (string) - 昵称
  - `avatar_url` (string) - 动态生成的头像 CDN URL
  - `gender` (integer) - 性别，枚举值见：`backend/app/enums/common.py` - `Gender`
  - `bio` (string) - 个性签名（可选）
  - `region` (string) - 地区（可选）

### 业务说明

- 返回列表默认排序：`last_message_time DESC`，`conversation_id ASC`
- `cursor` 为不透明字符串（Base64 编码的偏移量），前端只需在下一页请求中透传

---

## 获取单个联系人详情

### 基本信息

- **路径**: `GET /api/v1/contacts/{conversation_id}`
- **认证**: Bearer Token（必需）

### 路径参数

- `conversation_id` (string, 必填) - 对话ID

### 成功响应 (200)

```json
{
  "conversation_id": "conv_xyz789",
  "contact_qiao_id": "qiao_xm001",
  "alias": "小萌",
  "tags": ["朋友"],
  "remark": "很有趣的聊天伙伴",
  "is_pinned": false,
  "is_muted": false,
  "is_blocked": false,
  "profile": {
    "nickname": "小萌",
    "gender": 2,
    "avatar_url": "https://cdn.example.com/personas/qiao_xm001.webp",
    "bio": "喜欢音乐和电影",
    "region": "上海"
  }
}
```

**字段说明**:

- `conversation_id` (string) - 对话ID
- `contact_qiao_id` (string) - 联系人的qiao_id
- `alias` (string) - 备注
- `tags` (array) - 标签列表
- `remark` (string) - 描述
- `is_pinned` (boolean) - 是否置顶
- `is_muted` (boolean) - 是否免打扰
- `is_blocked` (boolean) - 是否屏蔽
- `profile` (object) - 联系人资料信息
  - `nickname` (string) - 昵称
  - `gender` (integer) - 性别，枚举值见：`backend/app/enums/common.py` - `Gender`
  - `avatar_url` (string) - 动态生成的头像 CDN URL
  - `bio` (string) - 个性签名
  - `region` (string) - 地区

### 错误响应

**400 Bad Request**:

- `"操作异常"` - 联系人不存在或无权访问

**500 Internal Server Error**:

- `"系统错误（error_code）"` - 服务器内部错误

---

## 更新联系人信息

### 基本信息

- **路径**: `PUT /api/v1/contacts/{conversation_id}`
- **认证**: Bearer Token（必需）

### 路径参数

- `conversation_id` (string, 必填) - 对话ID

### 请求参数

```json
{
  "alias": "新的备注",
  "tags": ["新标签1", "新标签2"],
  "remark": "新的描述",
  "is_pinned": true,
  "is_muted": false
}
```

**字段说明**:

- `alias` (string, 可选)
  - 备注
  - 显示宽度上限：24（约12个中文或24个英文）
  - 字符上限：32（按字符簇计数）
  - 传入 `null` 可清空备注

- `tags` (array, 可选)
  - 标签列表
  - 每个标签最长20字符
  - 传入 `[]` 或 `null` 可清空标签

- `remark` (string, 可选)
  - 描述
  - 显示宽度上限：400（约200个中文或400个英文）
  - 字符上限：400（按字符簇计数）
  - 传入 `null` 可清空描述

- `is_pinned` (boolean, 可选)
  - 是否置顶

- `is_muted` (boolean, 可选)
  - 是否免打扰

### 成功响应 (200)

```json
{
  "conversation_id": "conv_xyz789",
  "contact_qiao_id": "qiao_xm001",
  "alias": "新的备注",
  "tags": ["新标签1", "新标签2"],
  "remark": "新的描述",
  "is_pinned": true,
  "is_muted": false,
  "is_blocked": false,
  "profile": {
    "nickname": "小萌",
    "gender": 2,
    "avatar_url": "https://cdn.example.com/personas/qiao_xm001.webp",
    "bio": "喜欢音乐和电影",
    "region": "上海"
  }
}
```

### 错误响应

**400 Bad Request**:

- `"操作异常"` - 联系人不存在或无权访问
- `"参数错误"` - 请求参数格式错误

**500 Internal Server Error**:

- `"系统错误（error_code）"` - 服务器内部错误

### 业务说明

- 所有字段可选，支持部分更新
- 只更新传入的字段
- 未传入的字段保持不变

---

## 屏蔽联系人

### 基本信息

- **路径**: `POST /api/v1/contacts/{conversation_id}/block`
- **认证**: Bearer Token（必需）

### 路径参数

- `conversation_id` (string, 必填) - 对话ID

### 请求参数

无需请求体

### 成功响应 (200)

返回更新后的联系人详情，字段同 [获取单个联系人详情](#获取单个联系人详情)。

### 错误响应

**400 Bad Request**:

- `"操作异常"` - 联系人不存在或无权访问

**500 Internal Server Error**:

- `"系统错误（error_code）"` - 服务器内部错误

### 业务说明

- 屏蔽后不会收到对方的消息
- 不会删除联系人关系
- 不会删除聊天记录

---

## 取消屏蔽联系人

### 基本信息

- **路径**: `POST /api/v1/contacts/{conversation_id}/unblock`
- **认证**: Bearer Token（必需）

### 路径参数

- `conversation_id` (string, 必填) - 对话ID

### 请求参数

无需请求体

### 成功响应 (200)

返回更新后的联系人详情，字段同 [获取单个联系人详情](#获取单个联系人详情)。

### 错误响应

**400 Bad Request**:

- `"操作异常"` - 联系人不存在或无权访问

**500 Internal Server Error**:

- `"系统错误（error_code）"` - 服务器内部错误

---

## 删除联系人

### 基本信息

- **路径**: `DELETE /api/v1/contacts/{conversation_id}`
- **认证**: Bearer Token（必需）

### 路径参数

- `conversation_id` (string, 必填) - 对话ID

### 请求参数

无需请求体

### 成功响应 (204)

无返回体，删除成功后返回 HTTP 204 No Content。

### 错误响应

**400 Bad Request**:

- `"操作异常"` - 联系人不存在或无权访问

**500 Internal Server Error**:

- `"系统错误（error_code）"` - 服务器内部错误

### 业务说明

- 删除联系人关系
- 不删除聊天记录（客户端本地管理）
- 如果再次添加该联系人，会恢复联系人关系
