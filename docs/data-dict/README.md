# 数据库设计文档

## 设计原则

- 统一标识符命名：外部标识符统一使用`qiao_id`格式，内部使用Snowflake ID
- 枚举值使用整型：所有枚举字段使用TINYINT类型，在代码中定义枚举约束
- 核心业务表使用Snowflake ID：用户、消息、AI等核心表使用BIGINT类型的Snowflake ID
- 配置表使用自增ID：系统配置、统计等辅助表使用AUTO_INCREMENT
- 完善的索引设计：为高频查询字段添加合适的索引
- 时间字段自动管理：created_at和updated_at字段自动设置和更新
- 时间格式规范见 [时间格式规范](docs\spec\time-format.md)
