# AI对话配置

定义AI的性格、风格、关系等对话行为参数。

## ai_styles

AI风格表，定义 AI 实例的风格类型和评分维度。

```txt
id -- 自增ID
display_name -- 用于显示的名称
status -- 状态：1=active, 2=inactive
created_at
updated_at
```

## ai_dimensions

AI维度表，定义评分维度。

```txt
id -- 自增ID
name -- 用于通过llm响应查询的名称
display_name -- 用于显示的名称
description -- 用于管理后台参考
created_at
updated_at
```

## ai_style_dimensions

AI风格-维度关联表。

```txt
id
style_id  -- 关联 ai_styles.id
dimension_id  -- 关联 ai_dimensions.id
initial_position -- 该风格下的初始位置
created_at
```

## ai_dimension_relationship_mappings

AI关系映射表，定义风格评分与关系类型的映射关系。

```txt
id -- 自增ID
dimension_id -- 关联ai_dimensions.id
start_position -- 起始位置，0-1000千分比
end_position -- 结束位置，0-1000千分比
relationship_id -- 关联ai_relationships.id
priority -- 优先级，数字越小优先级越高
limit_count -- 出现的次数限制
created_at
updated_at
```

## ai_relationships

AI关系类型表，定义 AI 实例的关系类型。

```txt
id -- 自增ID
display_name -- 显示名称
prompt_fragment -- 提示词片段
status -- 状态：1=active, 2=inactive
wake_time_min_ms -- INTEGER NOT NULL DEFAULT 3000，微计时器下限（毫秒），CHECK >= 500
wake_time_max_ms -- INTEGER NOT NULL DEFAULT 3000，微计时器上限（毫秒），CHECK >= wake_time_min_ms
wake_time_bias -- VARCHAR(20) NOT NULL DEFAULT 'balanced'，响应时间倾向，CHECK IN ('balanced', 'centered', 'fast', 'slow', 'very_fast', 'very_slow')
wake_window_ms -- INTEGER NOT NULL DEFAULT 60000，跳过唤醒窗口（毫秒），CHECK >= 0
wake_time_adjustment -- VARCHAR(20) NOT NULL DEFAULT 'random_half'，等待时间调整策略
no_reply_probability -- DECIMAL(3,2) NOT NULL DEFAULT 0.00，不回复概率（0.00-1.00），CHECK >= 0 AND <= 1
followup_delay_ms -- INTEGER NOT NULL DEFAULT 5000，跟进消息延迟（毫秒），CHECK >= 0
created_at
updated_at
```

## ai_personalities

AI人格表，定义 AI 实例的人格特征和提示词模板。

```txt
id -- 自增ID
display_name -- 显示名称
prompt -- 人格提示词模板
json_schema -- JSON Schema 定义
status -- 状态：1=active, 2=inactive
created_at
updated_at
```

## ai_personality_placeholders

AI人格占位符表，定义人格模板中的占位符。是一种声明，在编辑其他内容时会对照此表检查。

```txt
id -- 自增ID
personality_id -- 关联ai_personalities.id
placeholder_key -- 占位符键名
display_name -- 显示名称
description -- 描述说明
example_value -- 示例值
is_required -- 是否必填：1=required, 0=optional
created_at
updated_at
```
