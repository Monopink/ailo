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
- [Doubao文档](../references/doubao-docs/)
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

**CAPTCHA 系统**:

当前状态:
- **管理后台**: 已启用 Cloudflare Turnstile
- **用户端/小程序**: 已禁用人机验证 (MVP阶段,小规模上线,欺诈风险低)

架构设计:
- 抽象接口: `CaptchaProvider` (factory.py)
- 支持 provider: `none` (禁用) | `turnstile` (Cloudflare Turnstile)
- 客户端特定配置: 通过 `X-Client` header 匹配 `{client}_captcha_provider` 配置

开发约束:
- **禁止**为用户端 API 添加验证逻辑 (除非明确需求变更)
- **禁止**假设系统支持未实现的 provider (如 aliyun)
- 扩展方式: 实现 `CaptchaProvider` 接口,在 factory.py 注册新 provider

配置说明:
- `admin_captcha_provider`: 管理后台 provider 选择
- `{client}_captcha_provider`: 未来预留客户端特定配置 (如 App)
- provider='none' 时,`require_human_verification=False`,跳过验证逻辑

## Docker 环境

**容器信息** (开发环境):
- 数据库容器: postgres (数据库名: ailo, 用户名: ailo_user, 端口: 5432)
- 后端容器: backend (端口: 8000, 代码热更新: 已启用)
- 工作目录: `deployment/`
- 配置文件: `docker-compose.yml`
- 环境变量: `.env` (项目根目录)

## 编程规范

**类型策略**:
- 函数必须有完整类型注解（参数与返回值）。
- 内部业务逻辑优先使用具体类型；遇到动态 JSON 则使用项目提供的 JSONDict/JSONValue 等别名。
- 处理外部 API(payload/SDK)、动态配置或框架限制时可以使用 dict[str, Any]，但必须在代码中注明数据来源（例如 # reason: PyJWT payload）并尽量封装在边界层。
- Any 仅在与第三方库或 Starlette Admin 等框架交互的边界存在，并应注明原因与替代方案；团队应保持透明以便逐步收敛。
- 泛型 ID 建议使用 int | str 或 TypeVar，避免无约束的 Any。
- ORM 相关数据可以使用 TypedDict 或 @dataclass(slots=True)，但不应重复 SQLAlchemy 模型；若多个模块依赖同一 TypedDict，请集中在 pp/type_defs 定义并记录数据来源。Admin 模块的特殊豁免可在 pp/admin/AGENTS.md 中查阅。
- 外部输入（API 请求、Webhook 等）仍然优先使用 Pydantic BaseModel 进行验证。

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

## 关键约束

<critical-rules>

### SQLAlchemy Async 关系访问规则

在异步上下文中访问 ORM 关系属性前必须使用 `.options(selectinload(...))` 等方式显式预加载，禁止依赖 `lazy="select"`。

❌ 错误示例 (会导致运行时错误):
```python
# Model definition
class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    contacts: Mapped[list["Contact"]] = relationship(lazy="select")  # 默认lazy加载

# 错误的访问方式
async def get_user_contacts(db: AsyncSession, user_id: int) -> list[Contact]:
    user = await db.get(User, user_id)
    # ❌ 运行时错误: greenlet_spawn has not been called
    return user.contacts
```

✅ 正确示例 (显式预加载):
```python
from sqlalchemy.orm import selectinload

async def get_user_contacts(db: AsyncSession, user_id: int) -> list[Contact]:
    result = await db.execute(
        select(User)
        .options(selectinload(User.contacts))  # 显式预加载
        .where(User.id == user_id)
    )
    user = result.scalar_one()
    return user.contacts  # 安全访问
```

**Model 定义建议**:
```python
# 异步ORM建议使用 lazy="raise" 避免意外的同步访问
class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    contacts: Mapped[list["Contact"]] = relationship(lazy="raise")  # 强制显式加载
```

### 禁止模块顶层实例化

禁止在模块顶层(import阶段)直接实例化应用对象、配置对象、数据库连接、客户端实例或其他可能带来副作用的实体。

❌ 错误示例 (会导致import副作用和测试困难):
```python
# ❌ bad_service.py
from app.core.database import SessionLocal
from openai import OpenAI
from app.core.config import settings

# 在模块顶层实例化,每次import都会执行
db = SessionLocal()  # 导致数据库连接泄露
client = OpenAI(api_key=settings.openai_api_key)  # 无法mock测试
config = load_config_from_file()  # import时就读取文件

async def process_data():
    # 使用全局实例
    result = await client.chat.completions.create(...)
    db.add(result)
```

✅ 正确示例 (使用工厂函数或依赖注入):
```python
# ✅ good_service.py
from functools import lru_cache
from openai import AsyncOpenAI
from fastapi import Depends
from app.core.database import get_db

# 使用 @lru_cache 延迟初始化单例
@lru_cache(maxsize=1)
def get_openai_client() -> AsyncOpenAI:
    """Get OpenAI client singleton (lazy initialization)."""
    from app.core.config import settings
    return AsyncOpenAI(api_key=settings.openai_api_key)

# FastAPI 依赖注入
async def process_data(
    db: AsyncSession = Depends(get_db),
    client: AsyncOpenAI = Depends(get_openai_client),
):
    result = await client.chat.completions.create(...)
    db.add(result)
```

### SQL 安全规则

项目默认禁止 f-string 拼接 SQL (S608),但少数文件有豁免(需安全审查)。

❌ 危险示例 (SQL注入风险):
```python
# ❌ 用户输入直接拼接到SQL
async def get_user(name: str):
    sql = f"SELECT * FROM users WHERE name = '{name}'"  # 注入风险!
    result = await db.execute(text(sql))
```

✅ 安全示例 (参数化查询):
```python
# ✅ 使用参数化查询
async def get_user(name: str):
    sql = "SELECT * FROM users WHERE name = :name"
    result = await db.execute(text(sql), {"name": name})

# ✅ 白名单验证 + 参数化
ALLOWED_COLUMNS = {"id", "name", "email"}
async def get_data(column: str, user_id: int):
    if column not in ALLOWED_COLUMNS:
        raise ValueError(f"Invalid column: {column}")
    # 列名验证后可安全拼接,值仍需参数化
    sql = f"SELECT {column} FROM users WHERE id = :user_id"
    result = await db.execute(text(sql), {"user_id": user_id})
```

**S608豁免申请要求**:
1. 必须在代码中注释说明安全性 (为何安全)
2. 必须在 pyproject.toml 中添加安全审查记录
3. f-string 中只能包含固定字符串片段,禁止包含任何用户输入
4. 所有动态值必须通过参数化传递

</critical-rules>

## 其他开发原则

- 不得使用任何已不推荐、过时、或在未来版本可能被移除的 API，禁用过时 API / Deprecated 写法
- 禁止使用黑魔法技巧，例如：Python 的动态修改模块、使用 getattr 拦截属性、运行时注入变量、猴子补丁（monkey patch）、隐式全局状态、隐式 lazy loading 等。所有代码必须采用清晰、显式、可维护的写法。

**Docstring 规范** (pydocstyle D rules):

渐进式要求:
- **API endpoints (app/api/)**: 必须添加 docstring，说明功能、参数、返回值
- **内部服务 (app/services/)**: 暂不强制要求 (per-file-ignores 豁免)
- **豁免规则**: D100(模块级)、D104(`__init__.py`)、D105(魔术方法)、D107(`__init__`方法)

API endpoint示例:
```python
@router.post("/login")
async def login(data: LoginRequest) -> LoginResponse:
    """User login endpoint.

    Args:
        data: Login credentials (mobile + verification code)

    Returns:
        LoginResponse: JWT token and user profile

    Raises:
        HTTPException: Invalid credentials or captcha verification failed
    """
    ...
```

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
