# AI 实例生命周期

本文档说明 AI 实例的创建、实例化和状态管理。

## 数据模型

**数据表定义** 详见：

- [../../data-dict/ai-instantiation.md](../../data-dict/ai-instantiation.md)
- [../../data-dict/profile.md](../../data-dict/profile.md)

**关系结构**：

- ai_personas (1) → (N) ai_templates
- ai_templates (1) → (N) ai_instances
- ai_personas (1) → (1) profiles (owner_type=2)
- ai_instances (1) → (1) profiles (owner_type=3, 仅手动创建)

## 核心概念

### AI Persona

实例原型，关联qiao_id与资料。

**职责**：

- 拥有唯一的 qiao_id（用户可见的实例标识）
- 关联一个 profile（owner_type=2）
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
- 存储用户特定的状态（memory、relationship_counts 等）
- 关联到 contacts 表（用户联系人）

**Profile 归属**：

- 正常流程创建：不拥有 profile，共享 persona 的 profile
- 手动创建：拥有独立的 qiao_id 和 profile（owner_type=3）

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
选择模板（优先不可复用）
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

异常：如果列表为空，请求挂起，等待管理员创建模板

**步骤 3：选择模板**

选择策略：

- 优先选择 reusable = false 的模板
- 如果都是 reusable = true，随机选择一个

输出：选中的 template 记录

**步骤 4：创建实例**

创建 ai_instances 记录：

- qiao_id = persona.qiao_id（继承，不生成新值）
- template_id = 选中的 template.id
- user_qiao_id = 当前用户的 qiao_id
- status = 1
- memory = NULL（初始为空）
- relationship_counts = {}（空 JSON 对象）
- typing_speed_wpm = template.typing_speed_wpm

注意：不创建 profile，共享 persona 的 profile

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
- 拥有独立的 profile（owner_type=3）
- 不受 persona/template 复用规则限制

**用途**：

- 测试
- 特殊定制实例
- 不在广场展示的实例

## 关键约束

**唯一性约束**：

- 同一用户不能重复添加同一个 qiao_id
- contacts 表有唯一索引：(user_qiao_id, contact_qiao_id)

**状态约束**：

- 只有 status=1 的 persona 和 template 可用于创建实例
- 不可复用的资源使用后立即标记为 exhausted

**数据一致性**：

- instance.qiao_id 必须等于 persona.qiao_id（正常流程）
- instance 不拥有 profile，通过 owner_type=2 查询 persona 的 profile
