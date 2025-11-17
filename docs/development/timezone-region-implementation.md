## AI 角色时区与地区字段改造方案

### 目标

1. **数据建模**：在 `ai_characters` 与 `ai_character_templates` 中新增时区 (`timezone`) 字段，提供默认值和后台配置入口。（地区字段暂不落地，等待后续需求再启用。）
2. **上下文处理**：LLM 会话消息合成时附带本地化时间标签，依据角色时区格式化历史记录与当前输入时间。
3. **系统占位符**：所有「当前时间」或相关模板占位符统一参照角色时区转换。
4. **扩展性**：地区字段仅存储位置标识（ISO 国家/城市等），为天气、新闻等后续能力预留数据，不承担时间换算职责。

### 字段设计

| 表 | 新字段 | 类型/约束 | 说明 |
| --- | --- | --- | --- |
| `ai_characters` | `timezone` | `VARCHAR(50)`，NOT NULL，默认 `Asia/Shanghai` | 存储 IANA 时区字符串，用于所有时间换算。 |
| `ai_character_templates` | `timezone` | 同上 | 用于角色初始化时继承默认时区。 |

> 若未来需要地区信息，可增加单独的 `location_metadata` JSON 字段，但 `timezone` 仍保持独立列以便校验与查询。

### 数据迁移

1. **Alembic 脚本**（`backend/database/migrations/xxxx_add_timezone_region.py`）：
   - `op.add_column` 为两个表新增列，`timezone` 设置默认 `'Asia/Shanghai'` 并更新历史记录。
   - 回滚时删除新增列。
2. **SQLAlchemy 模型**（`backend/app/models/ai/character.py` 等）：
   - 为 `AICharacter`、`AICharacterTemplate` 增加对应字段；在 `__table_args__` 中可选创建索引（例如 `(character_qiao_id, timezone)` 组合）。
3. **Admin 表单**：`ai_character_views`、`ai_character_template_view` 中添加输入控件：
   - 时区：下拉或可搜索列表（使用标准 IANA 时区清单），并在服务端验证。
   - 地区：文本或预设列表，暂时只做存储，不触发业务逻辑。

### 服务层改造

1. **上下文查询**：`services.ai.queries.get_character_context` 需要把 `timezone`、`region_code` 纳入返回结果，确保后台、LLM 构建与占位符均能使用同一份数据。
2. **时间格式化 Helper**：新增 `services.ai.utils.datetime.format_character_datetime(context, dt)`：
   - 输入 `CharacterContext`、UTC `datetime`，返回对应时区的 `datetime` 与友好字符串（如 `今天 13:24`、`昨天 09:05`、`2025-11-16 08:30`）。
   - 使用 `zoneinfo.ZoneInfo`（Python 3.12 标准库）处理时区；若配置无效则记录警告并回退至 `Asia/Shanghai`（UTC+8，Beijing）。
3. **会话上下文构建**：
   - `build_conversation_context` 在生成 `messages` 时调用 helper，将 `created_at` 格式化后拼入 `text_content`（如 `[昨天 13:24] 你好`）。
   - 可通过新增字段 `local_time_label` 来区分展示和内容，`ResponsesFormatConverter` 最终仍仅输出合并后的文本。
4. **LLM 当前输入**：`process_conversation` 在追加当前用户消息时，同样按角色时区计算时间标签后再拼接，避免测试页面与真实对话出现不一致。

### 系统占位符更新

1. **定位位置**：目前「当前时间」等占位符处理逻辑位于 `services.ai.conversation_prompt`（如 `build_system_prompt`、`build_response_schema`、模板变量替换）。
2. **统一入口**：新增函数 `resolve_current_time_placeholder(context)`：
   - 内部调用前述 helper 获取角色时区当前时间。
   - 支持返回多种格式（ISO、`YYYY-MM-DD HH:mm`、自然语言描述等），通过参数控制。
3. **调用点替换**：凡是读取系统时间填充 prompt/模板的地方都改成调用该函数，杜绝直接使用 `datetime.utcnow()`。

### 兼容性与回归

- 由于 `timezone` 默认 `UTC`，迁移后旧角色行为不变；只有在后台设置新时区后才会影响提示语与消息标签。
- `region_code` 目前仅存储，无业务读取，未来接入天气/新闻 API 时可直接复用该字段。
- 需回归以下流程：
  1. Admin 表单创建/编辑角色与模板，验证时区输入、默认值。
  2. `/ai_character/chat-test/` 在 persist/on 模式下历史消息是否带有正确的 `[时间]` 前缀。
  3. 模板占位符中「当前时间」与实际时区一致（例如在 Asia/Shanghai 时 13:00，UTC 字段应显示 05:00）。

### 后续扩展建议

- 若需要更精细的地区信息，可新建 `character_locations` 表（字段：`character_id`、`country_code`、`city_name`、`latitude`、`longitude`、`timezone`），通过外键/关联在 `CharacterContext` 中加载。
- 可以考虑在 `system_configs` 中提供全局默认时区、地区，角色/模板未设置时使用系统默认，保持灵活性。

---

以上方案覆盖字段设计、迁移、服务层与模板改造，符合当前 MVP 阶段的 KISS/YAGNI 原则，同时为未来天气/新闻等功能预留数据结构。待你审核后可按优先级开始实施。
