# AI实例化业务

管理AI角色的创建、分配和库存，包括类型、设定、模板和实例。

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

AI设定表，管理角色的唯一qiao_id（类似商品SKU）。

```txt
id -- Snowflake ID
qiao_id -- qiao_+随机字符，外部使用，唯一标识
type_id -- 关联ai_types.id（内部管理）
is_reusable -- 是否可以复用：1=reusable（多用户可添加）, 0=single_use（仅一个用户可添加）
status -- 状态：1=active, 2=inactive, 3=used
created_at
updated_at
```

## ai_templates

AI模板表，管理实例化时所需的 Prompt、记忆、维度配置与打字参数。

```txt
id -- 自增ID
type_id -- 关联ai_types.id（内部管理）
display_name -- 显示名称
style_id -- 关联ai_styles.id
personality_id -- 关联ai_personalities.id
memory -- 记忆设定
prompt_variables -- 占位符覆盖值，JSON格式
request_params -- LLM请求参数覆盖配置，JSONB格式，用于覆盖默认LLM设置
timezone -- 默认 IANA 时区标识（如 Asia/Shanghai），用于实例化拷贝
typing_speed_wpm -- 模板层的打字速度（词/分钟，整数，必填），角色创建时拷贝，运行阶段若遇到非法值再退回 35 WPM
position_mapping_config -- JSON格式，存储各维度的mapping配置,示例：
{
  "foo": {"algorithm": 1, "params": {}},
  "bar": {
    "algorithm": 2,
    "params": {
      "left_sensitivity": 5,
      "right_sensitivity": -3,
      "left_positive_gain": 45,
      "left_negative_gain": 39,
      "right_positive_gain": 45,
      "right_negative_gain": 39
    }
  }
}
is_reusable -- 是否可以复用：1=reusable（可创建多个角色）, 0=single_use（仅创建一次）
priority -- 优先级，数字越小优先级越高（不可复用模板优先）
status -- 状态：1=active, 2=inactive, 3=used（仅单次模板会被置为已使用）
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
style_id -- 关联 ai_styles.id
personality_id -- 关联 ai_personalities.id
status -- 状态：1=active, 2=inactive, 3=blocking
relationship_id -- 当前关系ID
relationship_counts -- 各关系类型使用次数统计，JSONB，如 {"friend":5,"lover":2}
memory -- 实例级记忆
prompt_variables -- 实例级占位符覆盖
request_params -- 实例级LLM请求参数覆盖
typing_speed_wpm -- 打字速度（词/分钟），默认沿用模板值
timezone -- IANA时区标识（如 Asia/Shanghai）
creation_metadata -- JSONB，创建时的完整快照（不可变），包含 source、persona_id、persona_qiao_id、persona_type_id、persona_type_name、persona_is_reusable、template_id、template_display_name、template_priority、assigned_at、assigned_by 等字段
created_by -- 创建者类型：1=user, 2=admin, 3=system
created_at
updated_at
```

**设计说明**：

- `user_id + qiao_id` 保证同一用户对同一 persona 只有一个实例（UNIQUE 约束）。
- `creation_metadata` 保存创建时的完整快照（persona、template、type 信息），用于审计和溯源，不受后续数据变更影响。
- 运行时只依赖 `qiao_id`（通过 profiles 获取展示信息）和实例自身的配置字段，不需要读取 persona 或 template 表。
- 所有与联系人、关系状态、消息记忆相关的字段仅保存在 `ai_instances`。
- persona 元数据（昵称、头像等）统一从 `profiles` 获取。

## ai_instance_dimensions

AI实例关系评分表，存储每个 `ai_instance` 的维度分值与位置。

```txt
id -- Snowflake ID
instance_id -- 关联 ai_instances.id
dimension_id -- 关联 ai_dimensions.id
score -- 当前分数值
position -- 千分比位置（0-1000）
position_mapping_algorithm -- 位置映射算法：1=直接映射, 2=V1独立双向偏移
position_mapping_params -- 位置映射参数（V1 算法必须提供 6 个字段）：
  {"left_sensitivity": 0, "right_sensitivity": 0, "left_positive_gain": 45, "left_negative_gain": 39, "right_positive_gain": 45, "right_negative_gain": 39}
created_at
updated_at
```
