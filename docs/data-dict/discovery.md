# 发现页（Square）

管理发现页的AI类型曝光配置。

## square_type_entries

Square 曝光表，决定哪些 `type_id` 被上架到 Square 以及采用何种曝光策略。

```txt
id -- 自增ID
square_category -- Square 分类枚举：backend/app/enums/common.py
type_id -- 关联 ai_types.id，代表被曝光的角色类型
exposure_strategy -- 曝光策略枚举：common.py
status -- common.py（inactive 时该 type_id 不出现在 Square）
created_at
updated_at
```

## 业务说明

Square 只消费该表的数据，与模板库存隔离；模板体系的状态不会直接影响 Square 曝光。接口端会根据 `type_id` 实时选择可用 persona/qiao_id，并直接复用 persona/profile 的展示信息。每个 Square 分类下，每个 AI 类型只能出现一次（UNIQUE 约束：square_category, type_id）。
