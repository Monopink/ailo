# 管理端（网页）原型文档

## 权限说明

- super_admin: 可以管理其他管理员，拥有所有权限
- admin: 有修改权限，可以管理业务数据
- viewer: 只有查看权限，无法修改数据

## 页面设计

### 登录页

简单的用户名密码登录，记录登录日志。

### 仪表盘

显示系统关键指标的概览页面。

#### 核心数据卡片

- 用户统计: 总用户数、今日新增用户、活跃用户数（日/周/月）
- 消息统计: 消息总数、今日消息数、平均每用户消息数
- AI统计: AI请求总数、今日AI请求数、启用的ai_personas数量
- 收入统计: 总收入、本月收入（未来功能）
- 订阅统计: 订阅用户数、本月新增订阅、本月退订（未来功能）

#### 趋势图表

- 用户增长趋势（近30天）
- 消息量趋势（近30天）
- AI请求量趋势（近30天）

#### 系统状态卡片

**显示内容**:

1. **LeanCloud服务状态**
   - ✅ 可达: 绿色图标 + "可达"文字
   - ❌ 不可达: 红色图标 + "不可达"文字 + 错误信息
   - 操作: [刷新] 按钮

2. **系统对话状态**
   - ✅ 已创建: 绿色图标 + "已创建"文字 + 对话ID
   - ⚠️ 未创建: 黄色图标 + "未创建"文字
   - ❌ 无效: 红色图标 + "无效"文字 + 错误信息
   - 操作: [刷新] 按钮

3. **最后检查时间**: 显示最近一次检查的时间

### 自定义页面

#### ai_instances（AI角色管理）

- 角色列表: 显示所有AI角色，支持按用户、状态筛选
- 对话测试：对指定AI角色发起。选定用户和模型配置后可以进行对话测试。
- 角色详情: 查看角色配置、关联的风格和人格
- 查看分数: 显示ai_instance_dimensions表数据
- 查看上下文: 显示ai_contexts表数据，AI对话历史
- 发送联系人申请: 管理员可以为无归属的AI角色向用户发送好友申请（2.0功能）
- 新增角色: 管理员可以创建新的AI角色（2.0功能）

##### 对话测试

作为AI角色的功能按钮，独立页面打开。

表单：

1. LLM Configuration（下拉菜单，包含所有可用的llm_configs）
2. 输入框：测试消息内容

不应该包含的表单：

1. AI角色选择（AI角色固定为当前角色）
2. 用户选择（每个AI角色最多只能有一个测试用户）

不能开始测试的情况：

1. AI角色缺少Profile
2. AI角色没有关联测试用户（type:vitual）或关联的不是测试用户
3. 测试用户没有Profile
4. 占位符验证出错误、Json Schema出错等验证问题

输出内容：

1. 对话记录
2. 请求记录（更新在request_logs表）

##### 分数算法测试

表单：

1. 算法选择（下拉菜单，写死的算法列表）
2. 偏移参数
3. 当前关系
4. 分数值Score*N（模拟LLM输出的分数，对应N个维度）
5. 最大分数值Score max*N（分数值的终点，用于计算position映射，对应N个维度）
6. 最小分数值Score min*N（分数值的起点，用于计算position映射，对应N个维度）

输出内容：

1. dimension_name
2. 没有经过算法偏移直接映射的position
3. 偏移后的positon
4. ai_relationship.display_name
5. ai_relationship.prompt_fragment

#### LLM 设计说明

- 同一个 Provider（如 doubao）可以有多个配置记录，通过 `display_name` 区分
- 例如：可以创建 "Doubao Production"、"Doubao Test"、"Doubao Backup" 等多个配置
- `name` 字段用于代码层面的 SDK 选择，`display_name` 用于 UI 显示和唯一标识

json_schema_mode 说明：

- 自动更新：此字段会在配置测试时根据实际响应格式自动更新
- 使用限制：AI Instance功能只能使用 `json_schema_mode='strict'` 的配置
- 测试流程：
  1. 新配置默认为 `'auto'`（未验证）
  2. 在配置测试页面进行测试
  3. 系统检测响应格式：
     - 如果返回JSON → 自动更新为 `'strict'`
     - 如果返回普通文本 → 自动更新为 `'disabled'`
  4. 测试结果会显示完整响应内容和JSON Schema支持状态
- 运行时保护：
  - 使用 `'auto'` 配置会提示"未验证，请先测试"
  - 使用 `'disabled'` 配置会提示"不支持JSON Schema，无法使用"
  - 如果 `'strict'` 配置返回非JSON，会自动更新为 `'disabled'` 并报错

API Key 管理：

- API Key 不存储在数据库中，而是存储在环境变量中
- `api_key_env` 字段指定环境变量名（如 `DOUBAO_PROD_API_KEY`）
- 如果 `api_key_env` 为空，则使用默认命名规则：`{NAME}_API_KEY`（如 `DOUBAO_API_KEY`）
- 这种设计既保证了安全性，又提供了灵活性

### 系统设置

包含系统参数配置管理。

#### 系统状态卡片

在配置页面顶部显示系统状态卡片，与首页Dashboard相同:

- LeanCloud服务状态 + [刷新]按钮
- 系统对话状态 + [刷新]按钮
- 最后检查时间

#### 系统对话管理

**显示内容**:

- 当前系统对话ID
- 创建时间
- Webhook URL (包含token)
- 警告提示

**操作按钮**:

- [重新初始化系统对话] 按钮
- [重新生成Webhook Token] 按钮
- [复制Webhook URL] 按钮

#### 配置管理

- 配置列表: 显示所有系统配置项
- 配置编辑: 修改配置值，支持不同数据类型（字符串、数字、布尔、JSON、枚举）
- 配置分类: 按功能模块分组显示（通过 `group_name` 字段动态分组）
- 配置历史: 记录配置变更历史（通过 `admin_operation_logs` 表追踪）

#### 配置类型

系统配置支持以下数据类型（`config_type` 字段）：

1. **字符串类型（STRING=1）**: 文本配置
2. **数字类型（NUMBER=2）**: 数值配置
3. **布尔类型（BOOLEAN=3）**: 开关配置
4. **JSON类型（JSON=4）**: 复杂对象配置
5. **枚举类型（ENUM=5）**: 受限选项配置（需配合 `allowed_values` 字段）

#### 主要配置项

**业务配置**:

- `default_contact_limit`: 默认联系人上限 (默认: 3)
- `contact_request_expiration_days`: 联系人请求过期时间（单位: 天，默认 3 天）
- `square_recommend_count`: 广场每次推荐的联系人数量 (默认: 10)
- `square_refresh_interval`: 广场刷新间隔/秒 (默认: 60)

**系统配置**:

- `max_message_length_chars`: 最大消息长度/字符 (默认: 49)
- `session_timeout`: 用户会话超时时间 (默认: 86400 秒 = 24 小时)

### 统计报表

基于各种stats表的数据分析。

#### 用户统计

- 用户增长: 基于stats_user_daily/weekly/monthly表
- 活跃度分析: 新增用户、活跃用户趋势
- 用户行为: 平均使用时长、功能使用情况

#### 消息统计

- 消息量分析: 基于stats_message_daily/weekly/monthly表
- 对话活跃度: 活跃对话数、平均消息数
- 消息类型分布: 文本、图片、表情等类型统计

#### AI统计

- AI使用情况: 基于stats_ai_daily/weekly/monthly表
- 请求量分析: AI请求数、成功率、响应时间
- 热门AI: 最受欢迎的AI角色和模板

#### 收入统计（未来功能）

- 收入趋势: 基于stats_revenue_daily/weekly/monthly表
- 订单分析: 订单量、平均订单金额
- 用户价值: 付费用户分析、ARPU等
