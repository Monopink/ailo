# 管理端 API（AI Personality Advanced Edit）

本文档定义 `ai_personality_advanced_edit` 页面使用的管理端接口契约。

> 约束：所有接口要求 Starlette-Admin 会话已登录。

---

## 1) 获取人格 Placeholder 列表

- **Method / Path**: `GET /admin-api/ai/ai-personality/{personality_id}/placeholders`
- **用途**: 加载该人格可用的 placeholder（人格专属 + 公共）

### Response

```json
[
  {
    "id": 101,
    "placeholder_key": "nickname",
    "display_name": "昵称",
    "description": "用户昵称",
    "example_value": "小橘",
    "is_required": false
  }
]
```

### 行为约束

- 返回按 `placeholder_key` 排序后的合并列表。
- `is_required` 返回布尔值。
- `id` 用于后续更新/删除。

---

## 2) 保存人格 Prompt + JSON Schema + Placeholder

- **Method / Path**: `POST /admin-api/ai/ai-personality/{personality_id}/save`
- **用途**: 一次提交页面编辑结果，保存 `prompt`、`json_schema` 与 placeholder 变更

### Request

```json
{
  "prompt": "你是{{self_profile}}，和对方关系是{{relationship_prompt}}。",
  "schema_config": {
    "dimensions": [
      {
        "name": "warmth",
        "min": 0,
        "max": 1000,
        "description": "关系温度"
      },
      {
        "name": "trust",
        "min": -100,
        "max": 300,
        "description": "互动中的信任水平"
      }
    ],
    "custom_fields": [
      {
        "name": "internal_thoughts",
        "type": "string",
        "description": "AI internal reasoning note",
        "required": false
      },
      {
        "name": "current_state",
        "type": "string",
        "description": "Current conversation state",
        "required": true
      }
    ]
  },
  "placeholders": [
    {
      "id": 21,
      "placeholder_key": "nickname",
      "display_name": "昵称",
      "description": "用户昵称",
      "example_value": "小橘",
      "is_required": true
    },
    {
      "id": null,
      "placeholder_key": "hobby",
      "display_name": "爱好",
      "description": "用户兴趣偏好",
      "example_value": "摄影",
      "is_required": false
    }
  ],
  "deleted_placeholder_ids": [31]
}
```

### Response

```json
{
  "success": true,
  "message": "Saved successfully",
  "updated_placeholders": 1,
  "created_placeholders": 1,
  "deleted_placeholders": 1
}
```

### 请求字段约束

- `prompt`：必填，去空白后不能为空。
- `schema_config`：必填对象。
- `schema_config.dimensions`：必填数组，定义 `score` 维度集合与每维范围。
- `schema_config.dimensions[].name`：必填，维度名（与 style 维度契约一致）。
- `schema_config.dimensions[].min/max`：必填数值，且 `min < max`。
- `schema_config.dimensions[].description`：可选字符串，写入 `json_schema.properties.score.properties.<dimension>.description`。
- `schema_config.custom_fields`：可选数组，定义管理员可选字段（如 `current_state` / `internal_thoughts`）。
- `schema_config.custom_fields[].name`：字段名不可重复；不得与固定系统字段冲突。
- `schema_config.custom_fields[].type`：JSON Schema 基础类型（`string`/`integer`/`number`/`boolean`/`object`/`array`）。
- `placeholders`：可选数组；带 `id` 视为更新，不带 `id` 视为新增。
- `deleted_placeholder_ids`：可选数组，按 ID 删除。

### 行为约束

- 保存为单事务：`prompt`、`json_schema`、placeholder 更新/新增/删除全部成功才提交。
- 更新/删除 placeholder 时必须校验 `personality_id` 归属，禁止跨人格写入。
- 当当前 personality 已被任意 instance 或 template 引用时，禁止变更 `score` 维度名称集合（新增、删除、改名）。
- 任一校验失败时返回错误且不产生部分提交。

### 典型错误

- `404 Personality not found`
- `400 schema_config is required`
- `400 dimensions are required`
- `400 duplicate dimension name: <name>`
- `400 cannot change personality score dimension set because this personality is referenced by instances or templates`
- `400 placeholder id cannot be both updated and deleted: [<id>]`

---

## 3) 获取 Style 维度集合

- **Method / Path**: `GET /admin-api/ai/ai_style/{style_id}/dimensions`
- **用途**: 作为人格 `score` 维度契约来源

### Response

```json
[
  {
    "id": 1,
    "name": "warmth",
    "display_name": "温暖度",
    "description": "关系温度"
  }
]
```

### 行为约束

- 返回指定 style 已关联维度。
- 结果按 `name` 排序。

---

## 4) 按维度名批量查询维度元数据

- **Method / Path**: `POST /admin-api/ai/ai-dimensions/by-names`
- **用途**: 根据 schema 中维度名回填 display_name/description

### Request

```json
{
  "names": ["warmth", "trust"]
}
```

### Response

```json
[
  {
    "id": 1,
    "name": "trust",
    "display_name": "信任度",
    "description": "互动中的信任水平"
  },
  {
    "id": 2,
    "name": "warmth",
    "display_name": "温暖度",
    "description": "关系温度"
  }
]
```

### 行为约束

- `names` 为空时返回空数组。
- 结果按 `name` 排序，不保证与请求顺序一致。

---

## 错误响应

管理端接口错误响应遵循 `detail + request_id` 规范，见 `docs/api/error-codes.md`。
