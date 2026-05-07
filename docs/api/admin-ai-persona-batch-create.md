# 管理端 Persona 批量创建接口

本文档定义管理端 `Persona Batch Create` 页面使用的接口契约。

## 接口概览

### 1) 提交单条队列

- **Method / Path**: `POST /admin-api/ai/persona-batch/submit-row`
- **认证**: Admin Session
- **请求类型**: `multipart/form-data`
- **用途**:
  - 新建条目：创建 persona，并补齐 persona/profile 字段
  - 编辑条目：在已存在 persona 上更新 persona/profile 字段

### 2) 消费导入令牌并加载编辑条目

- **Method / Path**: `POST /admin-api/ai/persona-batch/import-rows/consume`
- **认证**: Admin Session
- **请求参数**: Query `import_token` (string, 必填)
- **用途**: 消费一次性导入令牌，返回批量编辑初始行数据

## 提交单条队列请求字段

- `local_row_id` (可选, string): 前端队列本地条目 ID，原样回传
- `type_id` (必填, int): 目标 `ai_types.id`
- `nickname` (可选, string): 写入 `profiles.nickname`，空字符串视为 `NULL`
- `gender` (可选, string): `1|2|3`，写入 `profiles.gender`
- `bio` (可选, string): 写入 `profiles.bio`，空字符串视为 `NULL`
- `region` (可选, string): 写入 `profiles.region`，空字符串视为 `NULL`
- `tags` (可选, string): 预设标签，支持逗号分隔字符串或 JSON 字符串数组
- `remark` (可选, string): 写入 `ai_personas.remark`，空字符串视为 `NULL`
- `is_reusable` (可选, string): `0|1`，写入 `ai_personas.is_reusable`
- `persona_id` (可选, int): 已存在 persona 的 ID。提供后进入编辑条目模式
- `profile_id` (可选, int): 已存在 profile 的 ID。提供后用于定位资料行
- `avatar_file` (可选, file): 头像文件

## 提交单条队列响应体

```json
{
  "status": "success",
  "local_row_id": "row-1",
  "persona_id": "1024",
  "profile_id": "832746182736451584",
  "failed_step": null,
  "error_message": null,
  "avatar_url": "https://cdn.example.com/avatars/2026/05/xxx.webp"
}
```

### 字段说明

- `status`: `success` | `failed`
- `local_row_id`: 回传的本地条目 ID
- `persona_id`: persona ID（字符串）
- `profile_id`: profile ID（字符串）
- `failed_step`: 失败步骤标识
- `error_message`: 失败提示
- `avatar_url`: 提交后头像 URL（成功时返回）

### 失败步骤语义

- `create_persona`: 创建 persona 或校验 persona/type 关联失败
- `ensure_profile`: 定位或补齐 profile 失败
- `update_nickname`: 昵称校验失败
- `update_gender`: 性别校验失败
- `update_region`: 地区校验失败
- `update_tags`: 标签校验失败
- `update_remark`: 备注校验失败
- `update_is_reusable`: 复用性校验失败
- `upload_avatar`: 头像上传失败
- `request_validation`: 鉴权或请求参数异常
- `unknown`: 未分类服务端异常

## 消费导入令牌响应体

```json
{
  "items": [
    {
      "persona_id": "1024",
      "profile_id": "832746182736451584",
      "type_id": 7,
      "type_name": "朋友",
      "nickname": "小桥",
      "gender": 2,
      "bio": "喜欢散步和电影",
      "region": "上海",
      "tags": [
        "同城",
        "电影"
      ],
      "remark": "工作日晚上常在线",
      "is_reusable": 1,
      "avatar_url": "https://cdn.example.com/avatars/2026/05/xxx.webp"
    }
  ],
  "imported_count": 1
}
```

### 字段说明

- `items[].persona_id`: persona ID（字符串）
- `items[].profile_id`: profile ID（字符串，可空）
- `items[].type_id`: AI 类型 ID
- `items[].type_name`: AI 类型显示名
- `items[].nickname|gender|bio|region|tags|remark|is_reusable|avatar_url`: 编辑初始值
- `imported_count`: 返回条目数

## 导入令牌约束

- 令牌为一次性消费
- 令牌有效期固定为 900 秒
- 单次最多导入 500 条 persona
- 令牌仅可被创建该令牌的管理员消费
- 令牌存储于当前服务进程内存，服务进程重启后令牌失效
