# 管理端 API（AI Personality Advanced Edit）

本文档定义 `ai_personality_advanced_edit` 页面使用的管理端接口契约。

> 约束：所有接口要求 Starlette-Admin 会话已登录。

---

## 1) 获取高级编辑聚合配置

- **Method / Path**: `GET /admin-api/ai/ai-personality/{personality_id}/advanced-config`
- **用途**: 一次性返回页面初始化所需配置（personality 基础信息、统一字段条目、预设字段列表、保存约束）

### Response

```json
{
  "personality": {
    "id": 1,
    "display_name": "默认人格",
    "status": 1,
    "prompt": "你是{{self_profile}}。"
  },
  "field_entries": [
    {
      "key": "should_reply",
      "name": "should_reply",
      "group": "system_fixed",
      "type": "boolean",
      "required": true,
      "description": "是否要回复对方",
      "default_description": "是否要回复对方",
      "editable_description": true,
      "restorable": true,
      "deletable": false,
      "locked_name": true,
      "locked_type": true,
      "locked_required": true,
      "is_default": true
    },
    {
      "key": "score",
      "name": "score",
      "group": "score_root",
      "type": "object",
      "required": true,
      "description": "对当轮对话后对你对于这个维度的分数打分",
      "default_description": "对当轮对话后对你对于这个维度的分数打分",
      "editable_description": true,
      "restorable": true,
      "deletable": false,
      "locked_name": true,
      "locked_type": true,
      "locked_required": true,
      "is_default": true
    },
    {
      "key": "score:warmth",
      "name": "warmth",
      "display_name": "温暖度",
      "group": "score_dimension",
      "type": "integer",
      "required": true,
      "min": 0,
      "max": 1000,
      "description": "关系温度",
      "default_description": "关系温度",
      "editable_description": false,
      "restorable": false,
      "deletable": false,
      "locked_name": true,
      "locked_type": true,
      "locked_required": true,
      "is_default": true,
      "exists": true
    }
  ],
  "available_presets": [
    {
      "key": "internal_thoughts",
      "group": "system_preset",
      "name": "internal_thoughts",
      "type": "string",
      "default_description": "回复前的思考（整理你与对方的关系、对方的身份、意图，回复的原则，推荐20字左右，最多50字）",
      "default_required": false,
      "editable_description": true,
      "restorable": true,
      "locked_name": true,
      "locked_type": true,
      "locked_required": false
    }
  ],
  "constraints": {
    "is_referenced": true,
    "score_dimension_set_locked": true
  },
  "global_unique_placeholder_keys": ["signature", "company_name"]
}
```

### 行为约束

- `field_entries` 为统一字段模型，前端以 `group` 分组渲染。
- `field_entries.group = score_root` 表示 `json_schema.properties.score` 顶层字段；可编辑 description，并支持按字段恢复默认。
- `field_entries.group = score_dimension` 只读展示，不提供编辑入口。
- `field_entries(group=score_dimension).description` 读取优先级：
  1. personality `json_schema.properties.score.properties.<name>.description`
  2. `ai_dimensions.description`（当 personality schema 缺失时）
- `field_entries(group=score_dimension).description` 的运行时权威来源是 personality schema。
- `available_presets` 来源于后端代码注册表，不允许前端硬编码。
- `global_unique_placeholder_keys` 来源于 `system_configs.ai_global_unique_placeholder_keys`，用于 Placeholder 卡片“从全局唯一导入”候选与只读标注。

---

## 2) 获取人格 Placeholder 列表

- **Method / Path**: `GET /admin-api/ai/ai-personality/{personality_id}/placeholders`
- **用途**: 加载该人格可用的 placeholder

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

- 返回按 `placeholder_key` 排序的列表。
- `is_required` 返回布尔值。
- `id` 用于后续更新/删除。

---

## 3) 保存人格 Prompt + JSON Schema + Placeholder

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
    "standard_field_descriptions": [
      {
        "name": "should_reply",
        "description": "是否在本轮回复对方"
      },
      {
        "name": "memory_operations",
        "description": "记忆操作容器"
      }
    ],
    "score_description": "对当轮对话后对你对于这个维度的分数打分",
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
- `schema_config.dimensions[].description`：字符串；用于保存 `score` 子维度（`score.<dimension>`）description。
- `schema_config.standard_field_descriptions`：可选数组；用于提交系统固定字段 description 覆盖值。
- `schema_config.standard_field_descriptions[].name`：仅允许系统固定字段（不含 `score`）。
- `schema_config.standard_field_descriptions[].description`：字符串；字段级恢复默认后提交默认值。
- `schema_config.score_description`：可选字符串；用于提交 `score` 顶层字段 description，空值按默认描述处理。
- `schema_config.custom_fields`：可选数组，定义管理员可配置字段（包括系统预设字段与自定义字段）。
- `schema_config.custom_fields[].name`：字段名不可重复；不得与固定系统字段冲突。
- `schema_config.custom_fields[].type`：JSON Schema 基础类型（`string`/`integer`/`number`/`boolean`/`object`/`array`）。
- `placeholders`：可选数组；带 `id` 视为更新，不带 `id` 视为新增。
- `deleted_placeholder_ids`：可选数组，按 ID 删除。

### 行为约束

- 保存为单事务：`prompt`、`json_schema`、placeholder 更新/新增/删除全部成功才提交。
- 更新/删除 placeholder 时必须校验 `personality_id` 归属，禁止跨人格写入。
- 同一 personality 下 `placeholder_key` 必须唯一。
- 全局唯一检查来源为 `system_configs.ai_global_unique_placeholder_keys`，不由 personality placeholder 单条配置。
- 当当前 personality 已被任意 instance 或 template 引用时，禁止变更 `score` 维度名称集合（新增、删除、改名）。
- `ai_style` 侧更新 `ai_dimensions.description` 后，不自动同步已存在 personality schema。
- 任一校验失败时返回错误且不产生部分提交。

### 典型错误

- `404 Personality not found`
- `400 schema_config is required`
- `400 dimensions are required`
- `400 duplicate dimension name: <name>`
- `400 cannot change personality score dimension set because this personality is referenced by instances or templates`
- `400 placeholder id cannot be both updated and deleted: [<id>]`

---

## 4) 获取 Style 维度集合

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

## 5) 按维度名批量查询维度元数据

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
