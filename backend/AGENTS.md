# 后端开发规范

## 技术栈

- **语言**: Python 3.12
- **框架**: FastAPI
- **数据库**: PostgreSQL + SQLAlchemy (Async)
- **数据验证**: Pydantic v2
- **LLM服务**: Doubao (OpenAI SDK 兼容)
- **即时通讯**: Leancloud (仅消息传输)
- **管理后台**: Starlette Admin
- **数据迁移**: Alembic

## 参考资料

- [API文档](../docs/api/)
- [数据字典](../docs/data-dict/)
- [迁移操作](../docs/tech/MIGRATION.md)
- [Doubao文档](../references/doubao-docs/) - 特别提示：用户可以联系到Doubao文档专员，如果有不确定的问题请报告提问，请勿在一知半解状态实施
- [Leancloud文档](../references/leancloud-docs/)
- [管理后台开发规范](app/admin/AGENTS.md) - 修改 `app/admin/` 模块前必读

## 架构约束

**分层依赖规则** (从上到下):
```
orchestrators (编排层)
    ↓
relationship_scoring (关系评分)
    ↓
conversation_memory (对话记忆)
    ↓
ai_core (AI核心服务)
    ↓
repositories (数据访问层)
    ↓
models (数据模型)
```

依赖约束:
- 上层可以依赖下层，下层禁止依赖上层
- 同层之间禁止相互依赖
- 使用 import-linter 强制执行 (配置: `.importlinter`)

**Import 规则**:
- 能够绝对导入的，一律使用绝对导入
- 所有 import 必须在文件顶部 (除 TYPE_CHECKING 块)
- 禁止在函数内部 import

**Leancloud 集成规则**:
- Leancloud 仅用于消息传输，不存储业务逻辑
- 后端使用 REST API 调用
- 全局使用唯一系统对话 ID
- 业务数据必须存储在 PostgreSQL

## 配置与数据库

**配置管理**:
- 环境变量 (.env): 不会变更的配置、需要保证安全的配置 (API密钥等)
- 数据库表 (system_configs): 可能变更的配置、不涉及安全的配置

**迁移管理**:
- 统一使用 Alembic 系统
- 操作文档: [docs/tech/MIGRATION.md](../docs/tech/MIGRATION.md)

**同步更新要求**:

修改数据库 schema 后必须同步更新:
1. `backend/database/init/*.sql` - 初始化脚本
2. `docs/data-dict/*.md` - 数据字典文档

**数据库初始化**:

脚本位置: `backend/database/init/`

执行顺序:
1. `00_init_database.sh` - 初始化脚本
2. `01_schema.sql` - 表结构
3. `02_required_data.sql` - 必需数据
4. `03_sample_data.sql` - 示例数据 (可选)

注意: 初始化脚本仅在首次创建容器时执行，重新初始化需删除 volume。

## 认证与安全

**用户认证**:
- 非管理员用户: Hybrid 模式 (JWT + Token Store)
- 管理员用户: Starlette Admin 内置认证
- 管理后台: http://localhost:8000/qiao-dash/
- 默认账号: admin / admin123

**人机验证**:
- 使用阿里云 Captcha
- 应用场景: 短信发送等敏感操作

## Docker 环境

**容器信息** (开发环境):
- 数据库容器: postgres (数据库名: ailo, 用户名: ailo_user, 端口: 5432)
- 后端容器: backend (端口: 8000, 代码热更新: 已启用)
- 工作目录: `deployment/`
- 配置文件: `docker-compose.yml`
- 环境变量: `.env` (项目根目录)

## 编程规范

**类型注解**:
- 函数必须有完整类型注解 (参数和返回值)
- 禁止使用 `dict[str, Any]` 作为函数参数或返回值
- **严格禁止使用 `Any` 类型** - mypy 会报错 `[explicit-any]`
- 如果确实需要 `Any` (框架限制/SDK 未定型等), 必须立即向用户报告并说明原因，用户同意方案再增加忽略和注释说明
- 如果要忽略检查，在 pyproject.toml 中增加规则，非特殊情况不进行级忽略
- 使用项目定义的类型别名 (从 [type_defs](backend/app/type_defs/__init__.py) 导入):
  - JSON 类型: `JSONDict`, `JSONValue`, `JSONArray`, `JSONPrimitive`
  - 完整列表见 `backend/app/type_defs/__init__.py`
- 泛型 ID: 考虑 `int | str` 或 `TypeVar`
- 内部 ORM 数据: 使用 `TypedDict`，可选字段标记 `NotRequired[T | None]`
- 外部输入数据: 使用 Pydantic `BaseModel`
- 简单数据容器: 使用 `@dataclass(slots=True)`
- TypedDict 必须在工厂函数中集中构造，用文档字符串说明数据来源

**命名规范**:
- 函数/变量: snake_case
- 类: PascalCase
- 常量: UPPER_CASE
- 私有: 以下划线开头 `_private_function`
- 遵循 PEP8 要求

**函数式编程优先**:
- 优先使用无状态函数
- 避免使用类 (除 Model, Schema, Exception)
- 如需使用类，必须说明原因

**pendulum 使用**:
- 人性化时间显示、时区转换、相对时间判断、时间格式化等，使用 `pendulum`

## 其他开发原则

- SQLAlchemy Async 关系访问：在异步上下文中访问 ORM 关系属性前必须使用 `.options(selectinload(...))` 等方式显式预加载，禁止依赖 `lazy="select"`
- 不得使用任何已不推荐、过时、或在未来版本可能被移除的 API，禁用过时 API / Deprecated 写法
- 禁止使用黑魔法技巧，例如：Python 的动态修改模块、使用 getattr 拦截属性、运行时注入变量、猴子补丁（monkey patch）、隐式全局状态、隐式 lazy loading 等。所有代码必须采用清晰、显式、可维护的写法。
- 禁止在模块顶层（import 阶段）直接实例化应用对象、配置对象、数据库连接、客户端实例或其他可能带来副作用的实体。
  包括但不限于在模块顶部执行：db = SessionLocal(), engine = create_engine(db_url), client = OpenAI(api_key=...) 等。这些对象必须通过显式函数创建，例如工厂函数（如 create_app()）、依赖注入函数、或 @lru_cache() 包装的加载函数。

## 注释规范

- 注释应当避免的内容：
  - 写元注释，例如 `// Fix bug XX` 或 `// per request changed`
  - 写重复代码行为的注释，如 `// Increment i by 1`
  - 在最终提交中保留大块注释掉的旧代码。

## 质量检查

**代码修改后，必须执行以下检查流程，全部通过后才能报告"完成"。**

- 如果任何检查失败，必须立即修复，不得报告"已完成"
- 如果无法修复或不确定如何修复，立即停止工作并向用户说明情况
- 不得使用临时方案（如局部 import、type: ignore）绕过检查

### 快速检查（推荐）

```bash
# 只检查 git 修改的文件
./scripts/validate.sh --quick

# 完整系统验证（提交前运行）
./scripts/full_check.sh
```

### 改进策略 (临时)

**渐进式修复原则**:
- 在修改代码时，顺便修复相关的 ruff 问题
- 修改文件时，运行 `ruff check --fix <文件>` 自动修复
- 手动修复无法自动处理的问题
- 不使用 `# noqa` 或 `type: ignore` 绕过检查
- 优先修复高优先级问题
- 提交前确保修改的文件通过 ruff 检查
- **永远不要做只是为了通过检查的改动**
- **虽然修复范围只在改动的文件中，但是如果问题根源涉及其他文件，必须将问题相关文件一同修复，确保问题根源解决，而不是在改动的文件中打补丁**

### mypy 临时策略

- pre-commit 中的 mypy 目前只针对暂存文件执行，并附带 `--follow-imports=skip` 来避免历史报错阻塞提交
- 每个迭代至少手动运行一次 `mypy --config-file=pyproject.toml backend`，记录全局错误并安排清理任务
- 当 `backend` 目录下的类型错误清零后，需恢复全量检查（`pass_filenames: false` 且在 args 末尾追加 `backend`，同时移除 `--follow-imports=skip`）

### 单独工具

```bash
# 代码格式化和质量检查（自动修复）
ruff format backend/app/<文件>.py           # 格式化代码
ruff check --fix backend/app/<文件>.py      # 检查并自动修复问题

# 类型检查（必须通过）
mypy backend/app/<文件>.py --config-file pyproject.toml

# 架构契约检查（必须通过）
cd backend && lint-imports

# Import 位置检查（必须通过）
python scripts/check_local_imports.py backend/app/<文件>.py

# 语法检查（最基础）
python -m py_compile backend/app/<文件>.py
```

### 测试和健康检查

```bash
# Docker 健康检查
./scripts/check_docker.sh

# 运行测试
./scripts/run_tests.sh
./scripts/run_tests.sh --fast        # 快速测试
./scripts/run_tests.sh --coverage    # 生成覆盖率报告
```

## 测试体系

### 测试目录结构

```
backend/tests/
├── conftest.py              # pytest 配置和共享 fixtures
├── test_health.py           # 健康检查测试
├── test_database.py         # 数据库连接测试
└── test_api_basic.py        # 基础 API 测试
```

### 运行测试

```bash
# 运行所有测试
./scripts/run_tests.sh

# 仅运行快速测试
./scripts/run_tests.sh --fast

# 生成覆盖率报告
./scripts/run_tests.sh --coverage
```

### Docker 健康检查

```bash
./scripts/check_docker.sh
```

### 测试编写规范

- 测试文件命名: `test_<模块名>.py`
- 测试函数命名: `test_<功能描述>`
- 可用 fixtures: `db_session`, `client`, `auth_headers`
