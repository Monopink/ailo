# 后端开发规范

## 情况和开发原则

- 项目使用 [`import-linter`](.importlinter) 强制执行分层架构
- **SQLAlchemy Async 关系访问**：在异步上下文中访问 ORM 关系属性前必须使用 `.options(selectinload(...))` 等方式显式预加载，禁止依赖 `lazy="select"`。
- 注意遵守类型安全，即使代码能够运行也要遵守类型检查器的约束要求
- 使用无状态的函数式编程，如果需要使用类，请思考必要性并说明原因
- **你不得使用任何已不推荐、过时、或在未来版本可能被移除的 API，禁用过时 API / Deprecated 写法**，例如：
  - 禁止：Python 废弃的写法如datetime.utcnow()
  - 禁止：Pydantic v2已被移除的写法如min_items, max_items等
- 禁止使用黑魔法技巧，例如：Python 的动态修改模块、使用 getattr 拦截属性、运行时注入变量、猴子补丁（monkey patch）、隐式全局状态、隐式 lazy loading 等。所有代码必须采用清晰、显式、可维护的写法。
- 禁止在模块顶层（import 阶段）直接实例化应用对象、配置对象、数据库连接、客户端实例或其他可能带来副作用的实体。
  包括但不限于在模块顶部执行：db = SessionLocal(), engine = create_engine(db_url), client = OpenAI(api_key=...) 等。这些对象必须通过**显式函数**创建，例如工厂函数（如 create_app()）、依赖注入函数、或 @lru_cache() 包装的加载函数。
- 不允许未使用的变量或导入
- 遵循 PEP8 要求

## 注释规范

- 注释应当避免的内容：
  - 写元注释，例如 `// Fix bug XX` 或 `// per request changed`
  - 写重复代码行为的注释，如 `// Increment i by 1`
  - 在最终提交中保留大块注释掉的旧代码。

## 质量检查

详细内容见 [CODE_QUALITY_GUIDE.md](docs/tech/CODE_QUALITY_GUIDE.md)

**代码修改后，必须执行以下检查流程，全部通过后才能报告"完成"。**

- 如果任何检查失败，必须立即修复，不得报告"已完成"
- 如果无法修复或不确定如何修复，立即停止工作并向用户说明情况
- 不得使用临时方案（如局部 import、type: ignore）绕过检查

### 1. 语法检查（最基础，必须通过）

```bash
python -m py_compile backend/app/<修改的文件>.py
```

### 2. Import 规范检查（必须通过）

```bash
python scripts/check_local_imports.py backend/app/<修改的文件>.py
```

优先使用相对导入，合理和必要使用 TYPE_CHECKING

### 3. 代码格式化（自动修复）

```bash
# 自动格式化代码
black backend/app/<修改的文件>.py --config pyproject.toml

# 自动排序 imports
isort backend/app/<修改的文件>.py --settings-path pyproject.toml
```

### 4. 类型安全检查（必须通过）

```bash
mypy backend/app/<修改的文件>.py --config-file pyproject.toml
```

添加正确的类型注解，或修复类型不匹配的代码
(当前系统尚存大量问题，需要逐步清理，但新修改的代码必须完全通过)

### 5. 代码质量检查（必须通过）

```bash
pylint backend/app/<修改的文件>.py --rcfile pyproject.toml
```

逐个修复所有问题，确保 score ≥ 8.0
(当前系统尚存大量问题，需要逐步清理，但新修改的代码必须完全通过)

### 6. 架构契约检查（如果修改了 services/ai 目录）

```bash
cd backend && lint-imports
```

调整 import，确保单向依赖（上层→下层）
如果发现循环导入问题，重构代码结构，调整模块依赖关系

### 快速验证命令

修改多个文件后，使用快速验证脚本一次性检查所有修改：

```bash
# 只检查 git 修改的文件（推荐）
./scripts/validate.sh --quick

# 检查所有文件（全面检查）
./scripts/validate.sh
```

## 测试和验证体系

### 测试目录结构

```
backend/tests/
├── __init__.py
├── conftest.py              # pytest 配置和共享 fixtures
├── test_health.py           # 健康检查测试
├── test_database.py         # 数据库连接测试
├── test_api_basic.py        # 基础 API 测试
└── ...                      # 其他测试文件
```

### Docker 容器健康检查

**脚本**: `scripts/check_docker.sh`

检查 Docker 容器和服务的健康状态：

```bash
./scripts/check_docker.sh
```

### 运行测试

**脚本**: `scripts/run_tests.sh`

运行后端测试套件：

```bash
# 运行所有测试
./scripts/run_tests.sh

# 仅运行快速测试（排除慢速测试）
./scripts/run_tests.sh --fast

# 生成覆盖率报告
./scripts/run_tests.sh --coverage

# 详细输出
./scripts/run_tests.sh --verbose
```

### 完整系统验证

**脚本**: `scripts/full_check.sh` （推荐）

运行完整的系统验证，包括 Docker 健康检查、代码质量检查和测试：

```bash
# 完整验证（推荐在提交前运行）
./scripts/full_check.sh

# 快速验证（仅检查修改的文件）
./scripts/full_check.sh --quick

# 跳过 Docker 检查
./scripts/full_check.sh --skip-docker

# 跳过测试
./scripts/full_check.sh --skip-tests
```

### 测试编写指南

**测试文件命名**: `test_<模块名>.py`

**测试函数命名**: `test_<功能描述>`

**基本测试结构**:

```python
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_feature_name(client: AsyncClient):
    """Test description."""
    response = await client.get("/api/v1/endpoint")

    assert response.status_code == 200
    assert response.json()["key"] == "expected_value"
```

**可用 fixtures** (在 conftest.py 中定义):

- `db_session`: 数据库会话
- `client`: HTTP 客户端
- `auth_headers`: 认证头部
