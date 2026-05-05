# AI 实例生命周期

本文档说明 AI 实例的创建、实例化和状态管理。

## 数据模型

**数据表定义** 详见：

- 涉及数据表：`ai_types`, `ai_personas`, `ai_templates`, `ai_instances`, `profiles`

**关系结构**：

- ai_personas (1) → (N) ai_templates
- ai_templates (1) → (N) ai_instances
- ai_personas (1) → (1) profiles (owner_type=2)
- ai_instances (1) → (0..1) profiles (owner_type=3，手动创建或完整性修复)

## 核心概念

### AI Persona

实例原型，关联qiao_id与资料。

**职责**：

- 拥有唯一的 qiao_id（用户可见的实例标识）
- 可选 AI 用户名 `username`（非空时在 ai_personas 内大小写不敏感唯一；用于“按用户名搜索添加 AI”）
- 关联一个 profile（owner_type=2）
- 管理后台创建 persona 时必须同步创建最小 profile（空资料），禁止保留无 profile 的悬空 persona
- 通过 type_id 关联到 square_type_entries（广场展示）
- 控制是否可复用（reusable 字段）

**状态管理**：

- status=1 (active) - 可用于创建实例
- status=3 (exhausted) - 不可复用且已被使用

### AI Template

实例模板，定义 LLM 配置和 personality。

**职责**：

- 定义 llm_config_id（LLM 配置）
- 定义 personality_id（人格提示词）
- 定义 style_id（关系风格）
- 控制是否可复用（reusable 字段）

**状态管理**：

- status=1 (active) - 可用于创建实例
- status=3 (exhausted) - 不可复用且已被使用

### AI Instance

用户的 AI 联系人实例。

**职责**：

- 继承 persona 的 qiao_id（不生成新 qiao_id）
- `source=persona` 时写入 `persona_id` 绑定 persona；username 展示统一来源于 persona.username
- `source=persona` 时写入 `template_id` 绑定实例创建所使用的模板
- `source=admin_manual` 时 `persona_id` 必须为 `NULL`；username 展示为空
- 存储用户特定的状态（memory、relationship_counts 等）
- 关联到 contacts 表（用户联系人）

**Profile 归属**：

- 正常流程创建：不拥有 profile，共享 persona 的 profile
- 手动创建：拥有独立的 qiao_id 和 profile（owner_type=3）
- 完整性修复：若实例 qiao_id 下不存在可用 profile，系统必须自动补建最小 profile（owner_type=3）

**状态管理**：

- status=1 (active) - 正常使用
- status=2 (blocked) - 被 AI 主动删除（should_block=true）

## 用户添加流程

### 流程概述

```
用户在 Square 选择 qiao_id
  ↓
查找 ai_personas (by qiao_id)
  ↓
获取 type_id
  ↓
查找可用 ai_templates (by type_id, status=1)
  ↓
过滤当前用户已使用模板（包含已删除联系人历史）
  ↓
选择模板（优先不可复用，priority 小数优先，同优先级随机）
  ↓
创建 ai_instances
  ↓
写入 contacts
  ↓
更新模板和 persona 状态
  ↓
发送新联系人消息
```

### 详细逻辑

**步骤 1：查找 Persona**

输入：用户选择的 qiao_id

查询：ai_personas 表，条件 qiao_id = 输入值 AND status = 1

输出：persona 记录（包含 type_id、reusable）

**步骤 2：查找可用模板**

输入：persona.type_id

查询：ai_templates 表，条件 type_id = 输入值 AND status = 1

输出：可用模板列表

过滤：排除当前用户历史已使用的 template_id（包含已删除联系人对应实例）

异常：如果过滤后列表为空，请求挂起，等待管理员补充模板

**步骤 3：选择模板**

选择策略：

- 优先选择 reusable = false 的模板
- 按 priority 从小到大排序
- 同优先级随机选择一个
- 不可复用模板无可选项时，再对 reusable = true 的模板应用同样规则

输出：选中的 template 记录

**步骤 4：创建实例**

创建 ai_instances 记录：

- qiao_id = persona.qiao_id（继承，不生成新值）
- persona_id = persona.id（该流程固定 creation_metadata.source = "persona"）
- template_id = 选中的 template.id
- user_qiao_id = 当前用户的 qiao_id
- status = 1
- memory = NULL（初始为空）
- relationship_counts = {}（空 JSON 对象）
- typing_speed_wpm = template.typing_speed_wpm

注意：不创建 profile，共享 persona 的 profile

创建后必须执行完整性检查：若 `owner_qiao_id = instance.qiao_id` 查不到 profile，则自动创建最小 profile，防止对话链路因 profile 缺失中断。

**步骤 5：写入联系人**

创建 contacts 记录：

- user_qiao_id = 当前用户的 qiao_id
- contact_qiao_id = instance.qiao_id
- contact_type = 2（AI 联系人）
- status = 1

**步骤 6：更新状态**

如果 template.reusable = false：

- 更新 ai_templates.status = 3

如果 persona.reusable = false：

- 更新 ai_personas.status = 3

无论是否可复用：

- 更新 ai_personas.usage_count += 1

### Username 规则

- `ai_personas.username` 是 AI username 真相源（可为空；非空时唯一）。
- `ai_instances` 不存 username；通过 `persona_id` 关联读取 persona.username。
- `creation_metadata.source=persona`：`ai_instances.persona_id` 必须非空且指向有效 persona。
- `creation_metadata.source=admin_manual`：`ai_instances.persona_id` 必须为 `NULL`，username 展示为空。

**步骤 7：发送消息**

构建新联系人消息，通过消息系统发送

详见：[../message/leancloud.md](../message/leancloud.md)

## Profile 查询逻辑

### 正常流程创建的实例

查询条件：

- owner_qiao_id = instance.qiao_id
- owner_type = 2

结果：返回 persona 的 profile

### 手动创建的实例

查询条件：

- owner_qiao_id = instance.qiao_id
- owner_type = 3

结果：返回 instance 自己的 profile

## 状态转换

### Persona 状态

```
active (1)
  ↓ (不可复用 AND 被使用)
exhausted (3)
```

### Template 状态

```
active (1)
  ↓ (不可复用 AND 被使用)
exhausted (3)
```

### Instance 状态

```
active (1)
  ↓ (LLM 输出 should_block=true)
blocked (2)
```

## 手动创建实例

管理员可以手动创建特殊实例，不通过正常流程。

**特点**：

- 拥有独立的 qiao_id（不继承 persona）
- `qiao_id` 可由管理员手动填写；留空时系统自动生成
- 手动填写的 `qiao_id` 必须未被现有 persona 或 instance profile 占用
- `relationship_id` 由系统根据 style 自动初始化
- `persona_id` 固定为 `NULL`（手动实例不绑定 persona）
- username 展示为空
- 拥有独立的 profile（owner_type=3）
- 不受 persona/template 复用规则限制

**用途**：

- 测试
- 特殊定制实例
- 不在广场展示的实例

## 关键约束

**唯一性约束**：

- 同一用户不能重复添加同一个 qiao_id
- 同一用户不能重复使用同一个 template_id
- contacts 表有唯一索引：(user_qiao_id, contact_qiao_id)

**状态约束**：

- 只有 status=1 的 persona 和 template 可用于创建实例
- 不可复用的资源使用后立即标记为 exhausted

**数据一致性**：

- `creation_metadata.source=persona` 时：`instance.qiao_id` 必须等于 `persona.qiao_id`，`instance.persona_id` 必须等于 `persona.id`
- `creation_metadata.source=admin_manual` 时：`instance.persona_id` 必须为 `NULL`
- 对话运行时允许 profile 缺失降级（`self_profile` 置空），但创建链路必须强制补齐 profile
