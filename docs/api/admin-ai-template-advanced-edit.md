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
  "force_continue": false,
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
- `force_continue` (boolean, 可选，默认 `false`)
  - 用于确认“全局唯一占位符冲突”后继续保存
- `prompt_variables` (object, 可选)
- `position_mapping_config` (object, 可选)
- `memory_changes` (object, 可选)

### 激活校验

- 当且仅当发生 `非 ACTIVE -> ACTIVE` 状态切换时，触发校验。
- Personality 的必填 placeholders 必须在 `prompt_variables` 中具备非空值。
- 缺失时返回 400，`detail` 形如：
  - `Cannot activate template: missing required Prompt Variables (key_a, key_b)`

### 全局唯一占位符冲突校验

- 真相源配置：`system_configs.ai_global_unique_placeholder_keys`（字符串数组）。
- 保存时基于该配置执行全局同值检查，仅检查“当前 template 所属 personality 已定义且在全局列表内”的 placeholder key。
- 检查范围：全部 `ai_templates`（排除当前 `template_id`）。
- 仅检查 `prompt_variables` 中非空值。
- 比较规则：对值执行 `trim` 与换行归一化（`\r\n` → `\n`）后进行精确比较。
- 当配置项为空数组时，视为关闭全局唯一冲突检查。
- 当配置项结构异常（例如不是字符串数组，或数组内存在非字符串元素）时，跳过全局唯一冲突检查，并在成功响应 `warnings` 中返回告警。
- 当 `force_continue=false` 且命中冲突时，返回 409 并要求二次确认。
- 当 `force_continue=true` 时，允许在冲突存在的情况下继续保存。
- 当 `force_continue=true` 且命中冲突后继续保存时，会写入 `admin_operation_logs` 审计记录。

### 冲突响应（409）

```json
{
  "detail": "Global unique Prompt Variables conflict",
  "requires_confirmation": true,
  "conflicts": [
    {
      "placeholder_key": "signature",
      "normalized_value_preview": "Best friend forever",
      "duplicate_templates": [
        {
          "id": 12,
          "display_name": "Template A",
          "status": 1,
          "personality_id": 3,
          "personality_display_name": "Companion"
        }
      ],
      "duplicate_count": 1
    }
  ]
}
```

- `conflicts[].duplicate_templates` 返回前 20 条，完整数量由 `duplicate_count` 提供。

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

当全局唯一检查被跳过时：

```json
{
  "success": true,
  "message": "Data saved successfully",
  "memory_result": {
    "created": 0,
    "updated": 0,
    "archived": 0
  },
  "warnings": [
    {
      "code": "GLOBAL_UNIQUE_CHECK_SKIPPED",
      "reason": "invalid_config",
      "message": "Global unique check was skipped due to invalid system configuration. Please check ai_global_unique_placeholder_keys."
    }
  ]
}
```
