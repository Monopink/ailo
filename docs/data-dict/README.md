# 数据库设计文档

## 设计原则

- 统一标识符命名：外部标识符统一使用`qiao_id`格式，内部使用Snowflake ID
- 枚举值使用整型：所有枚举字段使用TINYINT类型，在代码中定义枚举约束
- 核心业务表使用Snowflake ID：用户、消息、AI等核心表使用BIGINT类型的Snowflake ID
- 配置表使用自增ID：系统配置、统计等辅助表使用AUTO_INCREMENT
- 完善的索引设计：为高频查询字段添加合适的索引
- 时间字段自动管理：created_at和updated_at字段自动设置和更新

## 文档索引

### 核心业务模块

- [user.md](user.md) - 用户体系（users, user_tokens, user_auths, login_records）
- [profile.md](profile.md) - 资料系统（profiles, user_profile_logs）
- [contact.md](contact.md) - 联系人（contacts, contact_requests）
- [message.md](message.md) - 消息（message_history, message_delivery_failures）
- [notification.md](notification.md) - 通知（notification_push_history）
- [discovery.md](discovery.md) - 发现页（square_type_entries）
- [security.md](security.md) - 安全（user_violation_logs, user_risk_stats）

### AI模块

- [ai-instantiation.md](ai-instantiation.md) - AI实例化业务（ai_types, ai_personas, ai_templates, ai_instances, ai_instance_dimensions）
- [ai-configuration.md](ai-configuration.md) - AI对话配置（ai_styles, ai_dimensions, ai_relationships, ai_personalities等）
- [ai-conversation.md](ai-conversation.md) - AI对话状态（ai_message_buffer, ai_conversation_state, ai_conversation_items等）

### LLM模块

- [llm.md](llm.md) - LLM配置（llm_providers, llm_configs, llm_test_logs）

### 系统模块

- [system-config.md](system-config.md) - 系统配置（system_configs）
- [system-stats.md](system-stats.md) - 统计报表（stats_*系列表）
- [admin.md](admin.md) - 管理后台（admin_users, admin_operation_logs, admin_login_logs）

### 未来功能

- [future-subscription.md](future-subscription.md) - 2.0功能（subscriptions, wallets, invitations等）

## 表关系概览

```
users (用户) ──┬── user_tokens (令牌)
               ├── user_auths (第三方绑定)
               ├── login_records (登录记录)
               ├── profiles (资料)
               ├── contacts (联系人)
               ├── ai_instances (AI实例)
               └── user_violation_logs (违规日志)

ai_instances ──┬── ai_conversation_state (对话状态)
               ├── ai_conversation_items (对话历史)
               ├── ai_message_buffer (消息缓冲)
               └── ai_request_logs (请求日志)

ai_templates ──── ai_instances (实例化)
ai_personas ───── ai_instances (实例化)
ai_types ──┬───── ai_personas (分类)
           └───── square_type_entries (广场曝光)

llm_providers ─── llm_configs (配置)
llm_configs ───── ai_request_logs (请求日志)
```
