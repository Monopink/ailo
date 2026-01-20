## 背景与现象
- 现象: LeanCloud Webhook 入站消息入库时报错 `MultipleResultsFound`。
- 根因: `ai_instances.qiao_id` 允许重复，但消息存储层仍按 `qiao_id` 单列查询 AIInstance 并要求唯一。
- 设计变更已生效: `ai_instances.qiao_id` 不再全局唯一，唯一约束应为 `(user_id, qiao_id)`。

## 目标
- 彻底移除基于 `qiao_id` 的 AI 实例唯一解析逻辑，改为会话上下文解析。
- 数据模型与代码实现一致，无历史遗留、无兼容分支、无回退路径。
- 文档/注释与实际一致，不保留已移除或不存在的内容。

## 方案（选定）
### 1) 以会话上下文解析参与者（强约束）
- 在消息入库路径中，以 `conv_id -> contacts` 为唯一事实来源。
- 根据 `contact.user_qiao_id` / `contact.contact_qiao_id` 与 `from_qiao_id` / `to_qiao_id` 的匹配关系，
  直接写入 `from_type/from_id/to_type/to_id`。
- 任何 `from_qiao_id` / `to_qiao_id` 与 `contact` 不匹配的情况直接报错，不再尝试回退查询。

### 2) 调整消息存储接口（禁止隐式解析）
- `store_message` / `_store_message_internal` 改为接收 `contact` 或显式的参与者元组。
- 删除或迁移旧的 `participant_resolver`（不再允许基于 `qiao_id` 单列查 AI）。
- `route_message` 直接传入 `contact`，避免重复查库。
- `send_message` 在有 `conv_id` 时强制加载 `contact` 并进行同样的解析，不允许缺失。

### 3) 数据模型一致性修正
- `AIInstance` 覆盖 `qiao_id` 字段，取消 `unique=True`，与设计一致。
- 清理数据库中 `ai_instances.qiao_id` 的唯一约束/索引（如存在）。
- 保持 `(user_id, qiao_id)` 唯一约束为唯一判定规则。

### 4) 清理不一致文档/注释
- 删除或修正文档/注释中指向不存在文件的内容。
- 仅保留真实存在且仍被使用的文档路径。

## 具体修改清单
- `backend/app/services/message/storage/persistence.py`
  - 接口签名调整、参与者解析改为 `contact` 规则。
- `backend/app/services/message/inbound/router.py`
  - 传入 `contact`，不再依赖旧解析器。
- `backend/app/services/message/outbound/sender.py`
  - 入库前按 `conv_id` 解析 `contact` 并写入参与者元组。
- `backend/app/services/message/storage/participant_resolver.py`
  - 移除或迁移至 `deleted/`，不保留遗留逻辑。
- `backend/app/models/ai/instance.py`
  - 覆盖 `qiao_id` 字段取消唯一约束。
- `backend/database/init/01_schema.sql`
  - 确保 `ai_instances.qiao_id` 非唯一。
- `docs/*`
  - 修正不存在的文档引用或补齐缺失文档（择一，确保一致）。

## 数据迁移与一致性
- 新建 Alembic 迁移:
  - 移除 `ai_instances.qiao_id` 唯一约束/索引（如存在）。
  - 校验 `(user_id, qiao_id)` 唯一约束完整。
- 若存在历史重复数据:
  - 按新规则允许重复，不做合并，不做兼容处理。

## 影响范围
- 消息入库链路（入站、出站）参与者解析逻辑。
- AIInstance 模型约束与 DB 约束。

## 风险与对策
- 风险: 上游传入的 `from_qiao_id/to_qiao_id` 与 `conv_id` 不一致。
- 对策: 强校验并报错，禁止回退查询，避免写入脏数据。

## 验证计划
- 触发 LeanCloud Webhook 入站消息，确认不再出现 `MultipleResultsFound`。
- 验证 `message_history` 中 `from_id/to_id` 与 `contacts` 映射一致。
- 运行后端验证流程（/validate-backend）。

## 状态
- Pending user approval for implementation.
