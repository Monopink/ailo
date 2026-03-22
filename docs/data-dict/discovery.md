# 发现页（Square）

管理发现页分类与上架映射。

## square_categories

Square 分类配置表。

```txt
id -- bigint 主键
category_key -- 分类键（kebab-case，唯一）
title -- 分类标题
description -- 分类描述
theme_key -- 主题键（enum: SquareCategoryTheme）
icon_ref -- 图标引用（tdesign:<icon-name>）
sort_order -- 排序值（升序）
status -- 状态（enum: SquareCategoryStatus）
created_at
updated_at
```

## square_type_entries

Square 上架映射表，决定分类内的 `type_id` 曝光。

```txt
id -- 自增ID
category_key -- 关联 square_categories.category_key
type_id -- 关联 ai_types.id
exposure_strategy -- 曝光策略（enum: ExposureStrategy）
status -- 状态（enum: SquareEntryStatus）
created_at
updated_at
```

## 约束

- `square_categories.category_key` 唯一。
- `square_categories.title` 长度上限为 20 字符。
- `square_type_entries` 上 `(category_key, type_id)` 唯一。
- `square_type_entries` 上 `status=1` 条件下 `type_id` 唯一。
