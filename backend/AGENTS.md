# Python 后端开发规则

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
- [代码检查](../docs/tech/CODE_QUALITY.md)
- [Doubao文档](../references/doubao-docs/)
- [Leancloud文档](../references/leancloud-docs/)

## 架构约束

### 分层依赖规则

**层级结构** (从上到下):
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

**依赖规则**:
- 上层可以依赖下层
- 下层禁止依赖上层
- 同层之间禁止相互依赖
- 使用 import-linter 强制执行 (配置: `.importlinter`)

### Import 规则

- 所有 import 必须在文件顶部
- 禁止在函数内部 import (除 TYPE_CHECKING 块)
- 优先使用相对导入
- 合理使用 TYPE_CHECKING 避免循环导入

### Leancloud 集成规则

- Leancloud 仅用于消息传输，不存储业务逻辑
- 后端使用 REST API 调用
- 全局使用唯一系统对话 ID
- 业务数据必须存储在 PostgreSQL

## 编程规范

### 函数式编程优先

- 优先使用无状态函数
- 避免使用类 (除 Model, Schema, Exception)
- 如需使用类，必须说明原因

### 类型注解

- 函数必须有完整类型注解 (参数和返回值)
- 禁止使用 `Any` 类型
- 使用 `| None` 而非 `Optional[T]`
- 使用 `dict[str, int]` 而非 `Dict[str, int]`
- 即使代码能运行也要遵守类型检查器约束

### SQLAlchemy Async 关系访问

- 访问 ORM 关系属性前必须显式预加载
- 使用 `.options(selectinload(...))` 等方式
- 禁止依赖 `lazy="select"`

### 命名规范

- 函数/变量: snake_case
- 类: PascalCase
- 常量: UPPER_CASE
- 私有: 以下划线开头 `_private_function`
- 遵循 PEP8 要求

### 模块初始化规则

禁止在模块顶层直接实例化:
- 应用对象
- 配置对象
- 数据库连接
- 客户端实例 (如 OpenAI client)
- 其他带副作用的实体

必须通过显式函数创建:
- 工厂函数 (如 `create_app()`)
- 依赖注入函数
- `@lru_cache()` 包装的加载函数

## 注释规范

禁止的注释:
- 元注释 (如 `# Fix bug XX`, `# per request changed`)
- 重复代码行为的注释 (如 `# Increment i by 1`)
- 大块注释掉的旧代码

## 配置管理

**环境变量** (.env):
- 不会变更的配置
- 需要保证安全的配置 (API密钥等)

**数据库表** (system_configs):
- 可能变更的配置
- 不涉及安全的配置

## 数据库操作

### 迁移管理

- 统一使用 Alembic 系统
- 操作文档: [docs/tech/MIGRATION.md](../docs/tech/MIGRATION.md)

### 同步更新要求

修改数据库 schema 后必须同步更新:
1. `backend/database/init/*.sql` - 初始化脚本
2. `docs/data-dict/*.md` - 数据字典文档

## 用户认证

- 非管理员用户: Hybrid 模式 (JWT + Token Store)
- 管理员用户: Starlette Admin 内置认证
- 管理后台: http://localhost:8000/qiao-dash/
- 默认账号: admin / admin123

## 人机验证

- 使用阿里云 Captcha
- 应用场景: 短信发送等敏感操作

## 提交前检查

```bash
# 快速检查修改的文件（推荐）
./scripts/validate.sh --quick

# 完整系统验证（提交前运行）
./scripts/full_check.sh
```

检查内容:
- 语法检查: `python -m py_compile`
- Import 位置: `check_local_imports.py`
- 代码格式和质量: ruff (自动修复)
- 类型检查: mypy (必须通过)
- 架构契约: import-linter (必须通过)

详细说明: [docs/tech/CODE_QUALITY.md](../docs/tech/CODE_QUALITY.md)

## 禁止行为

- ❌ 跳过代码检查 (validate.sh)
- ❌ 在函数内部 import (除 TYPE_CHECKING)
- ❌ 违反分层架构依赖规则
- ❌ 使用 `Any` 类型
- ❌ 函数缺少类型注解
- ❌ 使用类 (除必要场景)
- ❌ 在 Leancloud 存储业务逻辑
- ❌ 向后兼容 hack (MVP 阶段不需要)
- ❌ 使用过时或 deprecated API
  - 禁止: `datetime.utcnow()` (已废弃)
  - 禁止: Pydantic v1 写法 (如 `min_items`, `max_items`)
- ❌ 使用黑魔法技巧
  - 动态修改模块
  - getattr 拦截属性
  - 运行时注入变量
  - 猴子补丁 (monkey patch)
  - 隐式全局状态
  - 隐式 lazy loading
- ❌ 未使用的变量或导入
- ❌ 使用临时方案绕过检查 (如 `type: ignore`, `# noqa`)

## 开发原则

- 从最本质的角度，用第一性原理分析问题
- 使用正确的架构比最小修改更重要
- 简单至上 (KISS): 避免不必要的复杂性
- 精益求精 (YAGNI): 仅实现当前明确所需的功能
- 坚实基础 (SOLID): 单一职责、开放封闭、依赖倒置等
- 所有代码必须清晰、显式、可维护

## Docker 环境

### 容器信息 (开发环境)

- **数据库容器**: postgres_db_container
  - 数据库名: says
  - 用户名: says_user
  - 端口: 5432
- **后端容器**: backend_container
  - 端口: 8000
  - 代码热更新: 已启用

### 工作目录

- Docker Compose: `deployment/`
- 配置文件: `docker-compose.yml`
- 环境变量: `.env` (项目根目录)

### 数据库初始化

**脚本位置**: `backend/database/init/`

执行顺序:
1. `00_init_database.sh` - 初始化脚本
2. `01_schema.sql` - 表结构
3. `02_required_data.sql` - 必需数据
4. `03_sample_data.sql` - 示例数据 (可选)

**注意**: 初始化脚本仅在首次创建容器时执行，重新初始化需删除 volume。

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
