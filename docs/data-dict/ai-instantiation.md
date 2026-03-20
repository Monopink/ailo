# AI实例化业务

管理AI实例的创建、分配和库存，包括类型、设定、模板和实例。

## ai_types

AI类型表，用于内部管理分组。

```txt
id -- 自增ID
display_name -- 显示名称
description -- 描述说明
created_at
updated_at
```

## ai_personas

AI设定表，管理实例的唯一qiao_id（类似商品SKU）。

```txt
id -- Snowflake ID
qiao_id -- qiao_+随机字符，外部使用，唯一标识
username -- AI 用户名（用于搜索添加），5-20 位，规则同 users.username；在 ai_personas 域内按 LOWER(username) 唯一
type_id -- 关联ai_types.id（内部管理）
is_reusable -- 是否可以复用：1=reusable（多用户可添加）, 0=single_use（仅一个用户可添加）
status -- 状态：1=active, 2=inactive, 3=used
created_at
updated_at
```

## ai_templates

AI模板表，管理实例化时所需的 Prompt、维度配置与打字参数。

```txt
id -- 自增ID
type_id -- 关联ai_types.id（内部管理）
display_name -- 显示名称
style_id -- 关联ai_styles.id
personality_id -- 关联ai_personalities.id
prompt_variables -- 占位符覆盖值，JSON格式
request_params -- LLM请求参数覆盖配置，JSONB格式
llm_config_id -- 软引用到 llm_configs.id，NULL 表示实例化时走系统默认配置
timezone -- 默认 IANA 时区标识（如 Asia/Shanghai），用于实例化拷贝
typing_speed_wpm -- 模板层的打字速度（词/分钟，整数，必填），实例创建时拷贝，运行阶段若遇到非法值再退回 35 WPM
position_mapping_config -- JSON格式，存储各维度的mapping配置
is_reusable -- 是否可以复用：1=reusable（可创建多个实例）, 0=single_use（仅创建一次）
priority -- 优先级，数字越小优先级越高（不可复用模板优先）
status -- 状态：1=active, 2=inactive, 3=used（仅单次模板会被置为已使用）
created_at
updated_at
```

## ai_template_memories

AI模板记忆表，存储模板的种子记忆，在实例化时复制到实例记忆表。

```txt
id -- Snowflake ID
template_id -- 关联 ai_templates.id
memory_type -- core / recent
content -- 记忆内容，简洁描述
importance -- 重要性1-10，决定寿命（importance × 10 = 天数）
display_order -- 显示和复制顺序，数值越小优先级越高
created_at
updated_at
```

## ai_instances

AI实例表，存储"用户 × persona"实例化后的联系人。

```txt
id -- Snowflake ID
user_id -- 关联 users.id
user_qiao_id -- 用户的 qiao_id
qiao_id -- persona 的对外 ID（可重复，多个用户可添加同一 persona）
persona_id -- 关联 ai_personas.id；source=persona 时必须存在，source=admin_manual 时必须为 NULL
style_id -- 关联 ai_styles.id
personality_id -- 关联 ai_personalities.id
status -- 状态：1=active, 2=inactive, 3=blocking
relationship_id -- 当前关系ID
relationship_counts -- 各关系类型使用次数统计，JSONB，如 {"friend":5,"lover":2}
prompt_variables -- 实例级占位符覆盖
request_params -- 实例级LLM请求参数覆盖配置，JSONB格式
llm_config_id -- 实例自定义的 llm_configs.id，NULL 时运行期回落到系统主配置
typing_speed_wpm -- 打字速度（词/分钟），默认沿用模板值
timezone -- IANA时区标识（如 Asia/Shanghai）
creation_metadata -- JSONB，创建时的完整快照（不可变），包含 source、persona_id、persona_qiao_id、persona_type_id、persona_type_name、persona_is_reusable、template_id、template_display_name、template_priority、assigned_at、assigned_by 等字段
created_by -- 创建者类型：1=user, 2=admin, 3=system
created_at
updated_at
```

## ai_instance_dimensions

AI实例关系评分表，存储每个 `ai_instance` 的维度分值与位置。

```txt
id -- Snowflake ID
instance_id -- 关联 ai_instances.id
dimension_id -- 关联 ai_dimensions.id
score -- 当前分数值
position -- 千分比位置（0-1000）
position_mapping_algorithm -- 位置映射算法：1=直接映射, 2=V1独立双向偏移
position_mapping_params -- 位置映射参数
created_at
updated_at
```
