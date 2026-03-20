# AI 实例创建逻辑

AI 实例创建负责将 Persona + Template 组合创建为可用的 AI Instance，并建立联系人关系。

## 核心设计原则

### Persona + Template → Instance

- **Persona**：包含 qiao_id、类型、展示信息
- **Template**：包含 LLM 配置、系统提示词等
- **Instance**：实际运行的 AI 实例；`source=persona` 时继承 Persona 的 qiao_id，并写入 `persona_id` 绑定 persona（username 展示来源 persona.username）

**关系**：

- 一个 Persona 可以对应多个 Template（同一类型下）
- 一个 Template 可以创建多个 Instance（如果 is_reusable=1）
- 一个 Instance 只属于一个用户的一个联系人关系

### Instance 继承 Persona 的 qiao_id

**设计原因**：

- 用户添加的是 Persona 的 qiao_id（从 Square 获取）
- Instance 继承这个 qiao_id，保持一致性
- 不同用户添加同一个 qiao_id，后端创建不同的 Instance
- 用户无感知，认为添加的是同一个 AI

**实现**：

- `ai_instances.qiao_id = ai_personas.qiao_id`
- `creation_metadata.source = "persona"` 时：`ai_instances.persona_id = ai_personas.id`（username 展示来源 persona.username）
- `creation_metadata.source = "admin_manual"` 时：`ai_instances.persona_id IS NULL`（username 展示为空）
- 正常添加流程固定：`ai_instances.creation_metadata.source = "persona"`
- Instance 不创建新 Profile，共享 Persona 的 Profile

## 创建流程

### 1. AI 验证

Worker 处理 contact_request 时，首先验证 AI 是否可用：

**验证步骤**：

1. **查找 Persona**：
   - 通过 to_qiao_id 查询 ai_personas 表
   - 验证 persona 是否存在
   - 验证 persona.status = 1（可用）

2. **检查 Persona 可复用性**：
   - 如果 persona.is_reusable = 0（不可复用）
   - 检查 persona.status != 3（未被使用）
   - 如果已被使用，标记请求为 IGNORED

3. **查找可用模板**：
   - 查询 ai_templates 表
   - 条件：type_id = persona.type_id AND status = 1
   - 应用模板选择策略（见下文）

4. **判断结果**：
   - 有可用模板 → 继续创建流程
   - 无可用模板 → 挂起请求（见"模板不足挂起机制"）

### 2. 模板选择策略

**选择规则**：

1. **优先不可复用模板**：
   - 优先选择 is_reusable=0 的单次使用模板
   - 按 priority DESC 排序（数字越大优先级越高）
   - 同优先级随机选择一个
   - 使用 `FOR UPDATE SKIP LOCKED` 防止并发冲突

2. **回退到可复用模板**：
   - 如果没有不可复用模板
   - 对 is_reusable=1 的模板应用相同规则

3. **返回选中的模板或 NULL**

**优先级字段**：

- 字段：`ai_templates.priority`
- 类型：INTEGER
- 默认值：1
- 排序：DESC（降序）

**示例**：

假设有以下模板：

- 模板 A：priority=10, is_reusable=0
- 模板 B：priority=10, is_reusable=0
- 模板 C：priority=5, is_reusable=0
- 模板 D：priority=10, is_reusable=1
- 模板 E：priority=1, is_reusable=1

选择顺序：

1. 模板 A 或 B（随机选择，最高优先级且不可复用）
2. 模板 C（次高优先级，不可复用）
3. 模板 D（可复用，最高优先级）
4. 模板 E（可复用，最低优先级）

### 3. 创建 Instance

**创建步骤**：

1. **生成 Instance 记录**：
   - qiao_id = persona.qiao_id（继承）
   - persona_id = persona.id（绑定 persona；username 展示来源 persona.username）
   - type_id = persona.type_id
   - template_id = 选中的模板 ID
   - user_id = 申请人的 user_id
   - status = 1（激活）
   - creation_metadata = {"source": "persona", "persona_id": persona.id}

2. **不创建新 Profile**：
   - Instance 共享 Persona 的 Profile
   - Profile 的 owner_type=2, owner_id=persona.id

3. **标记模板状态**：
   - 如果 template.is_reusable = 0
   - 更新 template.status = 3（已使用）

4. **标记 Persona 状态**：
   - 如果 persona.is_reusable = 0
   - 更新 persona.status = 3（已使用）
   - persona.username 更新后实例侧无需同步字段（username 单一真相源）

### 4. 创建联系人记录

**创建步骤**：

1. **生成 Contact 记录**：
   - user_id = 申请人的 user_id
   - user_qiao_id = 申请人的 qiao_id
   - contact_type = AI (2)
   - contact_id = instance.id
   - contact_qiao_id = instance.qiao_id（即 persona.qiao_id）
   - alias = 申请时提供的 alias
   - tags = 申请时提供的 tags
   - source = contact_request.source

2. **生成 conversation_id**：
   - 格式：`conv_` + 随机字符串
   - 用于标识对话

3. **提交事务**

### 5. 更新请求状态

- contact_request.status = ACCEPTED
- 提交事务

## 模板不足挂起机制

当某个 AI 类型暂时没有可用模板时，请求不会被拒绝或失败，而是保持在 PENDING 状态并记录失败原因。

### 记录失败元数据

**字段**：

- `failure_code` - 失败原因代码
  - `NO_TEMPLATE_AVAILABLE` - 无可用模板
  - `MANUAL_PROVISION_REQUIRED` - 需要人工介入
- `failure_detail` - JSON 详情
  - 至少包含：ai_type_id、qiao_id、request_id
  - 方便后台定位问题
- `retry_count` - 重试次数（每次重试递增）
- `last_retry_at` - 最近一次重试时间

### Admin 视图

后台需要提供"待补库存"列表：

**筛选条件**：

- `status = PENDING`
- `failure_code IS NOT NULL`

**操作**：

- 管理员补充模板后，可直接触发"重试"
- 前端 contacts 视图也需要同样的按钮

### 重试逻辑

**触发方式**：

1. 管理员在后台手动触发
2. 用户重复提交相同请求（幂等）

**重试步骤**：

1. 清空 failure_code 和 failure_detail
2. 更新 last_retry_at = NOW()
3. 递增 retry_count
4. 重新执行模板选择流程

**重试结果**：

- 成功 → status = ACCEPTED，failure_* 字段保持 NULL
- 再次失败 → 重新写入 failure_code/failure_detail

### 用户端幂等

**行为**：

- 用户重复提交相同 (from_qiao_id, to_qiao_id) 的请求
- 系统不会新建 contact_requests
- 而是触发同一条记录的重试

**响应**：

- 客户端始终只收到：`{"message": "请求已发送"}`
- 无需了解挂起细节

**条件**：

- 如果上一条请求已过期或进入终态
- 新的请求会生成新的记录并重新走审批流程

## 并发控制

### FOR UPDATE SKIP LOCKED

**使用场景**：

- Worker 查询待处理请求
- 模板选择

**作用**：

- 防止多个 Worker 同时处理同一个请求
- 防止多个请求同时选择同一个不可复用模板

**实现**：

- 在事务中使用 `SELECT ... FOR UPDATE SKIP LOCKED`
- 锁定记录后立即标记状态（PROCESSING 或 status=3）
- 立即 commit，释放锁

### 事务管理

**关键设计**：PROCESSING 状态 + 独立 session

**问题**：如果在事务中锁定并处理，会导致长事务

**解决方案**：

1. 在事务中锁定请求
2. 立即标记为 PROCESSING 并 commit（释放锁）
3. 每个请求使用独立 session 处理
4. 处理失败不影响其他请求

**优势**：

- 避免长事务
- 防止重复处理（PROCESSING 状态保护）
- 支持水平扩展（多 Worker）
- 失败隔离

## 异常处理

### Persona 不存在

**处理**：

- 标记请求为 FAILED
- 记录 error 日志
- 这是系统错误，需要告警

### Persona 不可用

**处理**：

- 标记请求为 IGNORED
- 记录 info 日志
- 这是业务逻辑，不需要告警

### 模板不可用

**处理**：

- 挂起请求（status 保持 PENDING）
- 记录 failure_code 和 failure_detail
- 记录 warning 日志
- 等待管理员补充模板后重试

### 创建 Instance 失败

**处理**：

- 标记请求为 FAILED
- 记录 error 日志（带 exc_info=True）
- 回滚事务
- 需要告警

### 创建 Contact 失败

**处理**：

- 标记请求为 FAILED
- 记录 error 日志
- 回滚事务（包括 Instance）
- 需要告警

## 数据表

- [data-dict/ai-instantiation.md](../../data-dict/ai-instantiation.md) - ai_personas, ai_templates, ai_instances
- [data-dict/contact.md](../../data-dict/contact.md) - contact_requests, contacts
- [data-dict/profile.md](../../data-dict/profile.md) - profiles
