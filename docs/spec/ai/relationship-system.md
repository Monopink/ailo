# 关系系统

本文档说明关系分数计算、位置映射和关系选择逻辑。

## 数据模型

**数据表定义** 详见：

- [../../data-dict/ai-styles.md](../../data-dict/ai-styles.md)
- [../../data-dict/ai-style-dimensions.md](../../data-dict/ai-style-dimensions.md)
- [../../data-dict/ai-relationships.md](../../data-dict/ai-relationships.md)
- [../../data-dict/ai-dimension-relationship-mappings.md](../../data-dict/ai-dimension-relationship-mappings.md)
- [../../data-dict/ai-instance-dimensions.md](../../data-dict/ai-instance-dimensions.md)

## 核心概念

### Style

关系风格，定义关系演进模式。

**职责**：

- 定义该风格包含哪些 dimensions
- 每个 dimension 有独立的初始位置和映射参数

### Dimension

关系维度，如"亲密度"、"信任度"等。

**职责**：

- 定义维度名称和初始位置（initial_position）
- 定义 LLM 输出的分数范围（minimum/maximum）
- 存储位置映射参数（position_mapping_params）

### Relationship

关系等级，如"陌生人"、"朋友"、"恋人"等。

**职责**：

- 定义关系名称和提示词片段（prompt_fragment）
- 定义响应行为参数（wake_time_ms、followup_delay_ms 等）

### Mapping

维度到关系的映射规则。

**职责**：

- 定义 position 范围映射到哪个 relationship
- 定义优先级（priority）
- 定义使用次数限制（limit_count）

### Instance Dimension

实例的维度状态，存储当前分数和关系。

**职责**：

- 存储当前 score 和 position
- 存储当前 relationship_id
- 存储位置映射参数（继承自 dimension，可覆盖）

## 分数初始化

### 触发时机

当实例首次需要 relationship scores 时自动初始化。

调用位置：get_relationship_scores 函数发现实例没有 scores 时

实现位置：backend/app/services/ai/relationship.py

### 初始化逻辑

**步骤 1：获取 dimensions**

输入：instance.style_id

查询：ai_style_dimensions 表，条件 style_id = 输入值

输出：该 style 的所有 dimensions 列表

**步骤 2：为每个 dimension 创建记录**

对每个 dimension：

- score = dimension.initial_position
- position = dimension.initial_position
- position_mapping_params = dimension.position_mapping_params（复制）

**步骤 3：查找初始 relationship**

输入：dimension_id, initial_position

查询：ai_dimension_relationship_mappings 表

- 条件：dimension_id = 输入值
- 条件：start_position <= initial_position <= end_position

输出：匹配的 relationship_id

**步骤 4：处理异常情况**

如果找不到匹配的 relationship：

- relationship_id = NULL
- relationship_display_name = NULL
- 记录 ERROR 级别日志
- 对应的 {{relationship_prompt}} 占位符内容为空

**步骤 5：写入数据库**

创建 ai_instance_dimensions 记录并提交

## 分数计算和关系选择

### 输入验证

**输入**：LLM 输出的 score 对象（JSON）

**验证规则**：

- 数量和名称必须与 ai_style_dimensions 一致
- 每个维度必须有 minimum 和 maximum 定义
- minimum 不能等于 maximum
- 类型必须是整数

**异常处理**：

- 任何验证失败，记录错误日志并终止
- 最终结果为空关系（不更新）

### 步骤 1：分数映射

**目标**：将 LLM 输出的分数映射到 [0, 1000] 区间

**公式**：

```
mapped_score = ((score - minimum) / (maximum - minimum)) * 1000
```

**边界处理**：

- 映射后 clamp 到 [0, 1000]
- 结果取整

**异常处理**：

- 除零错误：记录错误并终止
- 参数不合法：记录错误并终止

### 步骤 2：位置映射

**目标**：将 mapped_score 通过位置映射算法转换为 position

**算法**：详见下文"位置映射算法"章节

**输出**：position 值（整数，范围 [0, 1000]）

### 步骤 3：候选收集

**目标**：找到所有 position 匹配的 relationships

**查询逻辑**：

对每个 dimension：

- 查询 ai_dimension_relationship_mappings
- 条件：dimension_id = 当前维度
- 条件：start_position <= position <= end_position
- 输出：匹配的 relationship 列表

合并所有维度的结果，去重

### 步骤 4：非当前关系过滤

**规则**：同一维度中，如果包含当前关系，则只保留当前关系

**逻辑**：

对每个 dimension：

- 如果候选中包含 current_relationship_id
  - 只保留 current_relationship_id
  - 过滤掉其他候选
- 如果不包含 current_relationship_id
  - 保留所有候选

**目的**：防止关系频繁跳变，保持稳定性

### 步骤 5：次数限制过滤

**规则**：根据 limit_count 和 relationship_counts 过滤

**逻辑**：

对每个候选 relationship：

- 获取 mapping.limit_count
- 获取 instance.relationship_counts[relationship_id]
- 如果 limit_count = NULL 或 0：无限制，保留
- 如果 counts >= limit_count：剔除
- 如果 counts > limit_count：剔除并记录错误日志（异常情况）

**目的**：限制某些关系的使用次数

### 步骤 6：优先级选择

**规则**：选择优先级数值最大的唯一关系

**逻辑**：

在筛选后的候选集合中：

- 找到最高优先级值
- 如果只有一个关系有此优先级：选中
- 如果多个关系并列最高优先级：记录错误，返回空关系
- 如果候选集合为空：记录错误，返回空关系

**异常处理**：

- 优先级并列：记录 ERROR 日志，不更新关系
- 候选为空：记录 ERROR 日志，不更新关系

### 步骤 7：结果落地

**更新 ai_instance_dimensions**：

- score = 计算得到的整数值
- position = 计算得到的整数值
- relationship_id = 选中的关系 ID
- relationship_display_name = 选中的关系名称

**更新 ai_instances.relationship_counts**：

- 仅当选择结果与当前关系不同时
- relationship_counts[relationship_id] += 1

**重要**：score 和 position 必须是整数

## 位置映射算法

### 算法版本

当前使用：位置映射算法 V1

实现位置：backend/app/services/ai/utils/position_mapping.py

### 设计目标

- 固定空间映射：使用 [0, 1000] 固定空间
- 镜像对称：左右两段相对于原点完美镜像
- 单调递增：score 增加时 position 单调递增
- 非线性加速：接近阈值时偏移加速增长
- 独立双向控制：可分别调整左段和右段的敏感度

### 核心参数

从 ai_instance_dimensions.position_mapping_params 获取：

**敏感度参数**（范围 -100 到 100）：

- left_sensitivity - 左段敏感度
- right_sensitivity - 右段敏感度

**增益参数**（范围 1 到 100）：

- left_positive_gain - 左段 sensitivity >= 0 时的对数增益
- left_negative_gain - 左段 sensitivity < 0 时的对数增益
- right_positive_gain - 右段 sensitivity >= 0 时的对数增益
- right_negative_gain - 右段 sensitivity < 0 时的对数增益

**原点**：

- initial_position - 从 ai_style_dimensions 继承

**约束**：所有参数必填，无默认值，缺失则抛出配置错误

### 算法步骤

**步骤 1：限制输入**

将 score 限制到 [0, 1000] 范围

**步骤 2：判断边界情况**

如果 initial_position = 0 或 1000：

- 直接返回 score，不进行偏移

如果 score = initial_position：

- 返回 initial_position，原点处无偏移

**步骤 3：判断敏感度边界**

选择对应的 sensitivity（左段或右段）

如果 sensitivity >= 100：

- offset_ratio = 1（完全偏移到边界）

如果 sensitivity <= -100：

- offset_ratio = 0（完全不偏移）

**步骤 4：计算归一化距离**

左段（score < initial_position）：

```
normalized_distance = (initial_position - score) / initial_position
```

右段（score > initial_position）：

```
normalized_distance = (score - initial_position) / (1000 - initial_position)
```

**步骤 5：计算阈值**

```
threshold = 1 - sensitivity / 100
```

范围：[0, 2]

**步骤 6：计算非线性偏移**

如果 normalized_distance >= threshold：

- offset_ratio = 1（超出阈值，完全偏移）

否则：

```
ratio = normalized_distance / threshold
offset_ratio = -gain * ln(formula) / 100
offset_ratio = clamp(offset_ratio, 0, 1)
```

其中 gain 根据左右段和正负 sensitivity 选择：

- 左段 sensitivity >= 0：left_positive_gain
- 左段 sensitivity < 0：left_negative_gain
- 右段 sensitivity >= 0：right_positive_gain
- 右段 sensitivity < 0：right_negative_gain

formula 根据情况选择：

- 大部分情况：1.12 - ratio
- 右段 sensitivity >= 0：1.12 - ratio / 2.5

**步骤 7：映射回原空间**

左段：

```
position = initial_position - initial_position * offset_ratio
```

右段：

```
position = initial_position + (1000 - initial_position) * offset_ratio
```

**步骤 8：边界保护**

将 position clamp 到 [0, 1000]，取整

### 参数含义

**sensitivity**：

- 100：最敏感，完全偏移到边界
- 0：标准敏感度，标准行为
- -100：最不敏感，完全不偏移

**threshold**（仅在 -100 < sensitivity < 100 时使用）：

- threshold > 1：不敏感，需要更大距离才能产生显著偏移
- threshold = 1：标准行为
- threshold < 1：敏感，较小距离就会产生显著偏移

**gain**：

- 增大 gain（接近 100）：偏移加速更快，更激进
- 减小 gain（接近 1）：偏移加速更慢，更保守

### 配置示例

**标准行为**（无性格偏移）：

```
left_sensitivity: 0
right_sensitivity: 0
left_positive_gain: 45
left_negative_gain: 39
right_positive_gain: 45
right_negative_gain: 39
```

**非常敏感**（两侧都容易触发偏移）：

```
left_sensitivity: 50
right_sensitivity: 50
left_positive_gain: 60
left_negative_gain: 50
right_positive_gain: 60
right_negative_gain: 50
```

**左侧敏感右侧迟钝**：

```
left_sensitivity: 30
right_sensitivity: -30
left_positive_gain: 70
left_negative_gain: 55
right_positive_gain: 35
right_negative_gain: 25
```

### 数值稳定性

使用 EPSILON (1e-10) 进行浮点数比较，避免：

- 除零错误
- 对数计算错误（ln(0) 或 ln(负数)）

## 反向计算

### 用途

用于 {{score:dimension_name}} 占位符，将 position 反向计算为 score

### 逻辑

通过位置映射算法的逆运算，从 position 推导出 score

详见实现：backend/app/services/ai/utils/position_mapping.py

## 关系响应参数

### 参数来源

从 ai_relationships 表获取，根据当前 relationship_id

### 关键参数

**唤醒等待**（详见 [../message/buffer.md](../message/buffer.md#唤醒机制)）：

- wake_time_ms - 唤醒等待时间
- wake_window_ms - 连续对话窗口
- wake_time_adjustment - 等待期间调整算法

**消息发送**（详见 [message-sending.md](message-sending.md)）：

- followup_delay_ms - followup_messages 延迟时间

**Prompt 构建**（详见 [prompt-building.md](prompt-building.md)）：

- prompt_fragment - 关系提示词片段

## 错误处理

### 配置错误

**触发条件**：

- 缺少必填参数
- 参数类型错误
- 参数范围错误（如 minimum = maximum）

**处理方式**：

- 记录 ERROR 日志
- 终止本次计算
- 不更新关系状态

### 映射错误

**触发条件**：

- 找不到匹配的 relationship
- 优先级并列
- 候选集合为空

**处理方式**：

- 记录 ERROR 日志
- 返回空关系
- 不更新关系状态

### 异常情况

**触发条件**：

- relationship_counts 超过 limit_count（数据不一致）

**处理方式**：

- 记录 ERROR 日志
- 剔除该候选
- 继续处理其他候选
