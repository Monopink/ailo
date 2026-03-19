# 管理端 API（AI Style Advanced Edit）

本文档定义 `ai_style_advanced_edit` 页面使用的管理端接口契约。

> 约束：所有接口要求 Starlette-Admin 会话已登录。

---

## 1) 获取 Style 维度集合

- **Method / Path**: `GET /admin-api/ai/ai_style/{style_id}/dimensions`
- **用途**: 返回指定 style 当前已关联的维度列表

### Response

```json
[
  {
    "id": 6,
    "name": "friendzhouchen",
    "display_name": "友情-周成",
    "description": "用于描述与周成的友情强度"
  }
]
```

### 行为约束

- 仅返回当前 style 已关联的维度。
- 结果按 `name` 排序。

---

## 2) 保存 Style 维度与关系映射

- **Method / Path**: `POST /admin-api/ai/ai_style/{style_id}/save`
- **用途**: 一次提交页面编辑结果，保存 style 与 dimension 的关联关系、dimension 元数据，以及对应的 relationship mappings

### Request

```json
{
  "dimensions": [
    {
      "dimension_id": 6,
      "initial_position": 50,
      "description": "用于描述与周成的友情强度"
    },
    {
      "temp_id": -1,
      "name": "trust_new",
      "display_name": "信任",
      "initial_position": 500,
      "description": "互动中的信任水平"
    }
  ],
  "removed_association_dimension_ids": [7],
  "mappings": [
    {
      "id": 22,
      "dimension_id": 6,
      "dimension_display_name": "友情-周成",
      "start_position": 50,
      "end_position": 150,
      "relationship_id": 10,
      "priority": 1,
      "limit_count": 0
    },
    {
      "dimension_id": -1,
      "dimension_display_name": "信任",
      "start_position": 0,
      "end_position": 1000,
      "relationship_id": 1,
      "priority": 2,
      "limit_count": 0
    }
  ],
  "deleted_mapping_ids": [31]
}
```

### Response

```json
{
  "success": true,
  "message": "Saved successfully",
  "updated_dimensions": 1,
  "created_dimensions": 1,
  "deleted_associations": 1,
  "deleted_dimensions": 0,
  "updated_mappings": 1,
  "created_mappings": 1,
  "deleted_mappings": 1
}
```

### 请求字段约束

- `dimensions`：数组，表示本次页面保留的维度集合。
- `dimensions[].dimension_id`：已存在维度的 ID；与 `temp_id` 二选一。
- `dimensions[].temp_id`：当前请求内的新建维度临时 ID，必须为负数整数；供 `mappings[].dimension_id` 引用。
- `dimensions[].name`：新建维度必填；必须是全局唯一维度名。
- `dimensions[].display_name`：新建维度时写入显示名；已有关联维度可省略，不省略时会更新元数据。
- `dimensions[].description`：可选；不为 `null` 时更新对应维度描述。
- `dimensions[].initial_position`：必填整数，范围 `0-1000`。
- `removed_association_dimension_ids`：数组，表示要从当前 style 解除关联的维度 ID。
- `mappings`：数组，表示本次页面保留的 mapping 集合。
- `mappings[].id`：已存在 mapping 的 ID；省略表示新建。
- `mappings[].dimension_id`：必填；可为已存在维度 ID，或当前请求中新建维度的负数 `temp_id`。
- `mappings[].start_position` / `mappings[].end_position`：必填整数，且满足 `0 <= start_position <= end_position <= 1000`。
- `mappings[].relationship_id`：必填，目标 relationship ID。
- `mappings[].priority`：整数，数值越小优先级越高。
- `mappings[].limit_count`：整数；`0` 表示不限次。
- `deleted_mapping_ids`：数组，表示要删除的 mapping ID。

### 行为约束

- `dimensions` 中的新建维度会先创建 `ai_dimensions` 记录，再建立 `ai_style_dimensions` 关联。
- `mappings` 为 dimension 级全局配置；修改或删除某个 mapping 会影响所有关联该 dimension 的 style。
- position 区间允许重叠。
- 保存前会检查每个 dimension 的 `initial_position` 是否能在命中的 mappings 中唯一决出最优先级关系。
- 若某个 dimension 的 `initial_position` 命中多个 mapping，且最小 `priority` 对应多个候选，则返回 `400` 并阻止保存。
- 维度与 style 关联先提交，随后再处理 mappings。

### 典型错误

- `404 Style not found`
- `400 initial_position is required for each dimension`
- `400 initial_position must be between 0 and 1000`
- `400 name is required for new dimensions`
- `400 dimension name already exists`
- `400 start_position is required for mapping`
- `400 end_position is required for mapping`
- `400 relationship_id is required for mapping`
- `400 Invalid start/end position for mapping`
- `400 Initial position 50 for dimension 友情-周成 matches multiple highest-priority mappings (priority=1): relationship_id=9 range=0-50, relationship_id=10 range=50-150`

---

## 3) 获取可关联的维度列表

- **Method / Path**: `GET /admin-api/ai/style/{style_id}/available-dimensions`
- **用途**: 为“关联 Dimension”弹窗提供当前 style 尚未关联的维度及其已有 mappings

### Response

```json
{
  "items": [
    {
      "id": 8,
      "name": "trust",
      "display_name": "信任",
      "description": "互动中的信任水平",
      "initial_position": null,
      "mappings": [
        {
          "id": 41,
          "start_position": 0,
          "end_position": 300,
          "relationship_id": 1,
          "priority": 2,
          "limit_count": 0
        }
      ]
    }
  ]
}
```

### 行为约束

- 仅返回当前 style 未关联的维度。
- `mappings` 返回该维度当前已有的全局 mappings，可用于关联前预览。
- `initial_position` 固定返回 `null`，由页面在关联时另行填写。

---

## 4) 查询其他使用同一维度的 Style

- **Method / Path**: `GET /admin-api/ai/style/{style_id}/dimension/{dimension_id}/other-styles`
- **用途**: 在编辑页面提示当前维度还被哪些其他 style 复用

### Response

```json
{
  "items": [
    {
      "id": 3,
      "display_name": "默认风格"
    },
    {
      "id": 5,
      "display_name": "熟人风格"
    }
  ],
  "count": 2
}
```

### 行为约束

- 返回值不包含当前 `style_id` 本身。
- `items` 按 `display_name` 排序。

---

## 错误响应

管理端接口错误响应遵循 `detail + request_id` 规范，见 `docs/api/error-codes.md`。
