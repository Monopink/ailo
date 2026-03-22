# 数据库设计文档

## 设计原则

- 统一标识符命名：外部标识符统一使用`qiao_id`格式，内部使用Snowflake ID
- 枚举字段统一在代码中定义：优先使用 `SMALLINT` + `IntEnum`；跨边界/稳定标识类枚举可使用 `VARCHAR` + `StrEnum`。data-dict 字段定义只标注 `enum: <EnumName>`，取值集合以 `backend/app/enums/*` 为准，避免重复与过时
- 核心业务表使用Snowflake ID：用户、消息、AI等核心表使用BIGINT类型的Snowflake ID
- 配置表使用自增ID：系统配置、统计等辅助表使用 PostgreSQL `IDENTITY`/sequence 自增
- 完善的索引设计：为高频查询字段添加合适的索引
- 时间字段自动管理：created_at和updated_at字段自动设置和更新
- 时间格式规范见 [时间格式规范](../spec/time-format.md)
