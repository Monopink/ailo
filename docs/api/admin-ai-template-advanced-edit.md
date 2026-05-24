# 管理端 AI Template Advanced Edit 接口

## 接口列表

- [保存模板高级编辑](#保存模板高级编辑) - `POST /admin-api/ai/ai_template/{template_id}/save`

## 相关文档

- `docs/spec/admin-panel/ai-advanced-edit.md`

---

## 保存模板高级编辑

### 基本信息

- **路径**: `POST /admin-api/ai/ai_template/{template_id}/save`
- **认证**: Admin Session（必需）
- **说明**: 保存模板高级编辑数据（状态、Prompt Variables、映射配置、记忆变更）。

### 路径参数

- `template_id` (integer, 必填) - 模板 ID。

### 请求体

```json
{
  "status": 1,
  "prompt_variables": {
    "name": "Alice"
  },
  "position_mapping_config": {
    "friendliness": {
      "algorithm": 1
    }
  },
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
  - `USED(3)` 不允许人工设置
- `prompt_variables` (object, 可选)
- `position_mapping_config` (object, 可选)
- `memory_changes` (object, 可选)

### 激活校验

- 当且仅当发生 `非 ACTIVE -> ACTIVE` 状态切换时，触发校验。
- Personality 的必填 placeholders 必须在 `prompt_variables` 中具备非空值。
- 缺失时返回 400，`detail` 形如：
  - `Cannot activate template: missing required Prompt Variables (key_a, key_b)`

### 成功响应（200）

```json
{
  "success": true,
  "message": "Data saved successfully",
  "memory_result": {
    "created": 0,
    "updated": 0,
    "archived": 0
  }
}
```
