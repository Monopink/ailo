# 发现页接口

## 接口列表

- [获取广场分类](#获取广场分类) - `GET /api/v1/discovery/square-categories`
- [获取广场联系人](#获取广场联系人) - `GET /api/v1/discovery/square`
- [获取陌生人详情](#获取陌生人详情) - `GET /api/v1/discovery/profile/{qiao_id}`

---

## 获取广场分类

### 基本信息

- **路径**: `GET /api/v1/discovery/square-categories`
- **认证**: Bearer Token（必需）

### 请求参数

无

### 成功响应 (200)

```json
{
  "items": [
    {
      "category_key": "friend",
      "title": "交友",
      "description": "结识同频的人，聊聊日常和心情",
      "theme_key": "blue",
      "icon_ref": "tdesign:user-filled"
    }
  ]
}
```

### 字段说明

- `items` (array)
  - `category_key` (string) - 分类键（kebab-case）
  - `title` (string) - 分类标题
  - `description` (string|null) - 分类描述
  - `theme_key` (string) - 主题键
  - `icon_ref` (string) - 图标引用（`tdesign:<icon-name>`）

### 相关文档

分类的筛选与排序规则见：`docs/spec/contact/square.md`

---

## 获取广场联系人

### 基本信息

- **路径**: `GET /api/v1/discovery/square`
- **认证**: Bearer Token（必需）
- **速率限制**:
  - 刷新请求（`refresh=true`）按 `user_qiao_id + category_key` 维度生效
  - 加载更多请求（携带 `cursor`）按 `user_qiao_id + category_key` 维度生效

### 请求参数

**查询参数**:

- `category_key` (string, 必填) - 分类键
- `cursor` (string, 可选) - 加载下一页的游标
- `feed_version` (string, 可选) - 当前 Feed 版本
- `refresh` (boolean, 可选) - 是否刷新并生成新 Feed 版本，默认 `false`
- `page_size` (integer, 可选) - 每页数量，默认取系统配置

### 成功响应 (200)

```json
{
  "items": [
    {
      "qiao_id": "qiao_xm001",
      "type_id": 101,
      "category_key": "friend",
      "nickname": "小萌",
      "gender": 2,
      "avatar_url": "https://cdn.example.com/personas/qiao_xm001.webp",
      "tags": ["交友", "朋友", "聊天"],
      "remark": null,
      "bio": "喜欢音乐和电影",
      "region": "上海"
    }
  ],
  "feed_version": "20260425161200543210",
  "next_cursor": "eyJ2IjoxLCJmIjoiMjAyNjA0MjUxNjEyMDA1NDMyMTAiLCJ0IjoxLCJzIjoiOGVmYzY4ZWQ2Y2NhOTNkYzFmMmY1YjA3ZjY0YjZiMjQiLCJxIjoicWlhb194bTAwMSJ9",
  "has_more": true,
  "refresh_available_at": "2026-04-25T07:12:10Z"
}
```

### 字段说明

- `items` (array)
  - `qiao_id` (string) - 联系人 qiao_id
  - `type_id` (integer) - AI 类型 ID
  - `category_key` (string) - 分类键
  - `nickname` (string|null) - 昵称
  - `gender` (integer|null) - 性别
  - `avatar_url` (string|null) - 头像 URL
  - `tags` (array) - 预设标签（写入联系人时的默认 tags）
  - `remark` (string|null) - 预设描述（写入联系人时的默认 remark）
  - `bio` (string|null) - 个性签名
  - `region` (string|null) - 地区
- `feed_version` (string) - 当前列表版本标识
- `next_cursor` (string|null) - 下一页游标
- `has_more` (boolean) - 是否有下一页
- `refresh_available_at` (string|null) - 下次可刷新时间（ISO 8601），仅刷新请求返回

### 相关文档

Square 列表的预设字段（`tags`、`remark`）生成规则见：`docs/spec/contact/square.md`

### 错误响应

- `400` - 请求参数错误
- `400` - 游标参数错误
- `429` - 请求过于频繁
- `500` - 系统错误

---

## 获取陌生人详情

### 基本信息

- **路径**: `GET /api/v1/discovery/profile/{qiao_id}`
- **认证**: 无需认证

### 路径参数

- `qiao_id` (string, 必填) - 陌生人 qiao_id

### 查询参数

- `category_key` (string, 可选) - 来源分类键

### 成功响应 (200)

```json
{
  "qiao_id": "qiao_abc123",
  "nickname": "小乔",
  "gender": 2,
  "avatar_url": "https://cdn.example.com/personas/qiao_abc123.webp",
  "tags": ["交友", "朋友", "聊天"],
  "remark": null,
  "bio": "喜欢和大家聊天",
  "region": "北京",
  "category_key": "friend",
  "category_title": "交友"
}
```

### 字段说明

- `qiao_id` (string)
- `nickname` (string|null)
- `gender` (integer|null)
- `avatar_url` (string|null)
- `tags` (array) - 预设标签（写入联系人时的默认 tags）
- `remark` (string|null) - 预设描述（写入联系人时的默认 remark）
- `bio` (string|null)
- `region` (string|null)
- `category_key` (string|null) - 分类键
- `category_title` (string|null) - 分类标题

### 相关文档

- 未传 `category_key` 时，返回 `category_key=null`、`category_title=null`。
- `category_key` 格式非法时返回 `400`（请求参数错误）。
- `category_key` 格式合法但无效或下线时，返回 `category_key=null`、`category_title=null`。
- `tags` 永远返回数组；无预设时返回 `[]`。
- `remark` 字段永远存在；无预设时返回 `null`。
- 预设字段生成规则见：`docs/spec/contact/square.md`

### 错误响应

- `400` - 参数错误
- `404` - 目标不存在
- `500` - 系统错误
