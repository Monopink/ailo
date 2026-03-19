# 关系系统

本文档只记录关系计算规则与边界，不重复数据字典和实现过程说明。

## 职责边界

- 字段定义与表结构：[`../../data-dict/ai-configuration.md#ai_styles`](../../data-dict/ai-configuration.md#ai_styles)、[`../../data-dict/ai-configuration.md#ai_style_dimensions`](../../data-dict/ai-configuration.md#ai_style_dimensions)、[`../../data-dict/ai-configuration.md#ai_relationships`](../../data-dict/ai-configuration.md#ai_relationships)、[`../../data-dict/ai-configuration.md#ai_dimension_relationship_mappings`](../../data-dict/ai-configuration.md#ai_dimension_relationship_mappings)、[`../../data-dict/ai-conversation.md#ai_instance_dimensions`](../../data-dict/ai-conversation.md#ai_instance_dimensions)
- `score` 输入来源与处理时序：[`llm-interaction.md`](llm-interaction.md)
- 关系参数在对话中的使用：[`../message/buffer.md`](../message/buffer.md)、[`message-sending.md`](message-sending.md)、[`prompt-building.md`](prompt-building.md)

## 核心不变量

- `score`、`position` 必须是整数，且落在 `[0, 1000]`。
- 关系计算维度集合必须与当前 style 的 dimensions 完全一致。
- 位置映射参数必须完整配置，不允许默认值或静默回退。
- 每次关系选择必须得到“唯一最高优先级”结果，否则本轮不更新关系。
- `relationship_counts` 仅在关系实际变更时递增。

## 初始化规则

- 触发：实例首次需要关系分数且不存在 `ai_instance_dimensions` 记录。
- 对每个 style dimension 创建实例维度状态：
  - `score = initial_position`
  - `position = initial_position`
  - `position_mapping_params` 复制自 dimension 配置
- style 保存时，若任一 dimension 的 `initial_position` 命中多个 mapping，且最小 `priority` 不唯一，则保存失败。
- 初始关系按现有关系选择引擎计算并持久化到 `ai_instances.relationship_id`。
- 实例创建后必须具备 `relationship_id`；若无法得到唯一关系（如无候选或优先级并列），创建流程失败。

## 分数计算与关系选择规则

### 输入约束

- `score` 对象必须覆盖且仅覆盖当前 style 的全部维度名。
- `score` 对象维度集合来源于当前 style。
- 每个维度必须具备合法 `minimum` / `maximum`，且 `minimum != maximum`。
- `minimum` / `maximum` 来源于 personality schema 的 `score.properties.<dimension_name>`。
- 维度分数必须是整数。
- 任一约束失败：报错并终止本轮处理。

### 计算顺序

1. 分数映射（LLM 分数 -> `[0, 1000]`）
2. 位置映射（`mapped_score` -> `position`）
3. 候选收集（`position` 命中 mapping）
4. 非当前关系过滤（稳定性约束）
5. 使用次数限制过滤（`limit_count`）
6. 优先级唯一选择
7. 结果落地

### 分数映射

```
mapped_score = ((score - minimum) / (maximum - minimum)) * 1000
```

- 映射结果必须 clamp 到 `[0, 1000]` 并取整。
- 分母非法或参数错误视为配置错误，本轮终止更新。

### 候选与过滤规则

- 候选收集：按 `dimension_id + position` 命中所有 mapping。
- 非当前关系过滤：在同一维度候选中若包含当前关系，仅保留当前关系。
- 次数限制过滤：
  - `limit_count = NULL` 或 `0` 表示不限次
  - `counts >= limit_count` 时剔除
  - `counts > limit_count` 视为数据异常，记录错误并剔除

### 优先级选择与落地

- 仅允许“唯一最高优先级”候选获选。
- 若最高优先级并列或候选为空，本轮关系不更新。
- 落地时更新 `ai_instance_dimensions.score/position/relationship_*`。
- 仅在关系发生变化时更新 `ai_instances.relationship_counts[relationship_id] += 1`。

## 位置映射算法 V1

### 设计约束

- 固定映射空间 `[0, 1000]`。
- 映射方向保持单调：输入分数上升时输出位置不下降。
- 左右两侧可独立配置敏感度与增益。
- 所有映射参数必填；缺失即配置错误。

### 参数

- `initial_position`（原点，来自 dimension）
- `left_sensitivity`、`right_sensitivity`（范围 `[-100, 100]`）
- `left_positive_gain`、`left_negative_gain`、`right_positive_gain`、`right_negative_gain`（范围 `[1, 100]`）

### 计算流程

1. 将输入 `score` clamp 到 `[0, 1000]`。
2. 边界处理：
   - `initial_position` 为 `0` 或 `1000` 时直接返回 `score`
   - `score == initial_position` 时返回 `initial_position`
3. 按左右段选择 `sensitivity`：
   - `sensitivity >= 100`：`offset_ratio = 1`
   - `sensitivity <= -100`：`offset_ratio = 0`
4. 常规区间计算归一化距离：

```
# 左段（score < initial_position）
normalized_distance = (initial_position - score) / initial_position

# 右段（score > initial_position）
normalized_distance = (score - initial_position) / (1000 - initial_position)
```

5. 计算阈值：

```
threshold = 1 - sensitivity / 100
```

6. 计算偏移：
   - `normalized_distance >= threshold` 时：`offset_ratio = 1`
   - 否则：

```
ratio = normalized_distance / threshold
offset_ratio = -gain * ln(formula) / 100
offset_ratio = clamp(offset_ratio, 0, 1)
```

7. `gain` 选择规则：
   - 左段且 `sensitivity >= 0`：`left_positive_gain`
   - 左段且 `sensitivity < 0`：`left_negative_gain`
   - 右段且 `sensitivity >= 0`：`right_positive_gain`
   - 右段且 `sensitivity < 0`：`right_negative_gain`
8. `formula` 选择规则：
   - 默认：`1.12 - ratio`
   - 右段且 `sensitivity >= 0`：`1.12 - ratio / 2.5`
9. 映射回原空间：

```
# 左段
position = initial_position - initial_position * offset_ratio

# 右段
position = initial_position + (1000 - initial_position) * offset_ratio
```

10. 将 `position` clamp 到 `[0, 1000]` 并取整。

### 数值稳定性

- 使用 `EPSILON (1e-10)` 进行浮点比较。
- 必须避免除零与 `ln(<=0)`。

## 反向计算规则

- `{{score:dimension_name}}` 需要从 `position` 反向推导 `score`。
- 反向计算必须与 V1 正向算法保持同一参数集与边界行为。

## 关系响应参数

- 参数来源：当前 `relationship_id` 对应的 `ai_relationships` 记录。
- 关键参数：
  - 唤醒：`wake_time_ms`、`wake_window_ms`、`wake_time_adjustment`
  - 发送：`followup_delay_ms`
  - Prompt：`prompt_fragment`

## 错误边界

- 配置错误（缺参、类型错误、范围错误）：报错并终止本轮处理。
- 映射错误（无候选、优先级并列、无匹配关系）：返回空关系结果，不更新状态。
- 数据异常（`relationship_counts > limit_count`）：记录错误并剔除该候选，继续处理其余候选。
