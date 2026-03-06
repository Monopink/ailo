# 页面内容接口

## 接口列表

- [批量获取页面内容](#批量获取页面内容) - `GET /api/v1/pages`
- [获取单个页面内容](#获取单个页面内容) - `GET /api/v1/pages/{page_key}`

---

## 批量获取页面内容

### 基本信息

- **路径**: `GET /api/v1/pages`
- **认证**: 无需认证
- **Headers**:
  - `X-Client` (必填): 客户端标识，当前固定 `mini-program`

### 请求参数

**查询参数**:

- `page_keys` (string, 必填)
  - 逗号分隔的 `page_key` 列表
  - 服务端按首次出现顺序处理，并对重复键去重
  - 任一 `page_key` 不存在时，整包请求失败（all-or-nothing）

### 成功响应 (200)

```json
{
  "items": [
    {
      "page_key": "user_agreement",
      "page_category": 1,
      "title": "用户协议",
      "locale": "zh-CN",
      "content_rendered_format": "html",
      "content_rendered": "<h1>用户协议</h1><p>...</p>",
      "updated_at": "2026-03-06T09:20:00Z"
    }
  ]
}
```

**字段说明**:

- `page_key` (string) - 页面标识
- `page_category` (int) - 页面分类（见 `backend/app/enums/common.py::AppPageCategory`）
- `title` (string) - 页面标题
- `locale` (string) - 语言，当前固定 `zh-CN`
- `content_rendered_format` (string) - 渲染格式，当前固定 `html`
- `content_rendered` (string) - 渲染后的页面正文
- `updated_at` (string) - 最后更新时间（ISO 8601）

### 错误响应

**400 Bad Request**:

- 缺少 `X-Client`
- `page_keys` 为空或格式无效

**404 Not Found**:

- 请求的任一 `page_key` 未命中有效页面

**500 Internal Server Error**:

- `"系统错误（error_code）"` - 服务器内部错误

---

## 获取单个页面内容

### 基本信息

- **路径**: `GET /api/v1/pages/{page_key}`
- **认证**: 无需认证
- **Headers**:
  - `X-Client` (必填): 客户端标识，当前固定 `mini-program`

### 路径参数

- `page_key` (string, 必填) - 页面标识

### 成功响应 (200)

```json
{
  "page_key": "user_agreement",
  "page_category": 1,
  "title": "用户协议",
  "locale": "zh-CN",
  "content_rendered_format": "html",
  "content_rendered": "<h1>用户协议</h1><p>...</p>",
  "updated_at": "2026-03-06T09:20:00Z"
}
```

### 错误响应

**400 Bad Request**:

- 缺少 `X-Client`
- `page_key` 格式无效

**404 Not Found**:

- 页面不存在或未启用

**500 Internal Server Error**:

- `"系统错误（error_code）"` - 服务器内部错误

## 业务说明

- 页面展示接口不返回 `content_md`。
- `client_type` 仅由 `X-Client` 推导。
