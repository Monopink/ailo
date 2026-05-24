# 管理端 AI Instance Advanced Edit 接口

## 接口列表

- [保存实例高级编辑](#保存实例高级编辑) - `POST /admin-api/ai/ai_instance/{instance_id}/save`

## 相关文档

- `docs/spec/admin-panel/ai-advanced-edit.md`

---

## 保存实例高级编辑

### 基本信息

- **路径**: `POST /admin-api/ai/ai_instance/{instance_id}/save`
- **认证**: Admin Session（必需）
- **说明**: 保存实例高级编辑数据（Prompt Variables、维度配置、关系、状态、记忆变更）。

### 路径参数

- `instance_id` (integer, 必填) - 实例 ID。

### 请求体（示例）

```json
{
  "status": 2,
  "prompt_variables": {
    "name": "Alice"
  },
  "dimensions": [],
  "positions": {},
  "relationship_id": null,
  "memory_changes": {
    "create": [],
    "update": [],
    "archive_ids": []
  }
}
```

### 字段说明

- `status` (integer, 可选)
  - 仅允许 `1=ACTIVE`、`2=INACTIVE`
  - `BLOCKED(3)` 不允许人工设置
- `prompt_variables` (object, 可选)
- `dimensions` (array, 可选)
- `positions` (object, 可选)
- `relationship_id` (integer | null, 可选)
- `memory_changes` (object, 可选)

### 成功响应（200）

```json
{
  "success": true,
  "message": "Saved successfully",
  "updated_dimensions": 0,
  "created_dimensions": 0,
  "memory_result": {
    "created": 0,
    "updated": 0,
    "archived": 0
  }
}
```
