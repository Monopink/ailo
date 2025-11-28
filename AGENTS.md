# 开发原则

## 设计理念

这是一个基于AI的拟人聊天软件，逻辑和界面向微信靠拢。已IM软件的风格包装AI对话功能。并且希望让AI角色能够有真人对话的节奏、语气、情感等感觉。产品体验的核心是拟人化和真实感,对外避免“AI/机器人”字眼。

## 项目简介

- 现在项目在MVP开发阶段，我开发经验不足，主要依赖AI开发，并且整个项目只有我一个负责。
- 代码实施应该始终遵守产品原型文档,[原型文档目录](docs\prototype) [技术文档目录](docs\development)。如果你发现原型设计存在问题或不详细的地方应该立即提出，而不是自行修改实现。
- 后端使用Python 3.12[fast-api](backend\app),数据库使用PostgreSQL,前端包括基于Flutter的iOS App(未来), [微信小程序](frontend\wx-minipg)等
- LLM服务使用Doubao,使用兼容Openai SDK的调用方式
- 消息服务使用Leancloud即时通讯服务,但是只是作为消息传送不承载业务逻辑,与系统解耦,便于未来替换
  - Leancloud后端使用RestAPI调用,小程序使用Java SDK调用,全局使用唯一系统对话ID
- 管理后台使用Starlette Admin [开发环境地址](http://localhost:8000/qiao-dash/) 用户名为admin 密码admin123
- 数据迁移统一使用 Alembic 系统，[操作文档](docs/README_MIGRATION.md)
- 在发送短信等操作时，需要进行人机验证，暂时使用阿里云Captcha
- 暂未选定短信验证码发送服务商
- [数据库初始化脚本](backend\database\init)
- 配置管理使用环境变量+数据库表system_configs管理的方式，不会变更、需要保证安全的设置项在环境变量，其他设置项在数据库
- 用户（非管理员用户）登录验证方式为Hybrid模式。JWT+Token store模式
- 项目使用 [`import-linter`](.importlinter) 强制执行分层架构

相关参考内容:[Doubao文档目录](references\doubao-docs), [Leancloud文档目录](references\leancloud-docs), [Leancloud示例Web Demo目录](references\leancloud-message-web-demo),[starlette-admin源码及文档](references\starlette-admin)

## Docker 和数据库操作

### Docker Compose 基本信息

**工作目录**: `deployment/`
**配置文件**: `docker-compose.yml`
**环境变量**: `.env` (位于项目根目录)

### 容器信息（开发环境）

- **数据库容器**: `postgres_db_container`
  - 数据库名: `says`
  - 用户名: `says_user`
  - 端口: `5432`
  - Volume: `says_dev_postgres_data`

- **后端容器**: `backend_container`
  - 端口: `8000`
  - 代码热更新: 已启用，无需频繁重启

### 数据库初始化脚本

**位置**: `backend/database/init/`

执行顺序：

1. `00_init_database.sh` - 初始化脚本（自动执行）
2. `01_schema.sql` - 数据库表结构
3. `02_required_data.sql` - 必需的系统数据（开发环境）
4. `03_sample_data.sql` - 示例测试数据（可选，通过 `LOAD_SAMPLE_DATA` 环境变量控制）

**注意**: 初始化脚本仅在首次创建容器时执行。如需重新初始化，必须删除 volume。

### Alembic 数据库迁移

详细文档: [docs/README_MIGRATION.md](docs/README_MIGRATION.md)

## 遵守的原则

- 现在项目在MVP开发阶段，不需要任何的向后兼容。杜绝设置不应该的默认值、回退值而隐藏可能发生的错误的行为
- 从最本质的角度，用第一性原理来分析问题
- 使用正确的架构比最小修改更重要
- 优先使用工具解决问题
- API和前端展示给用户的信息应该简洁，不暴露内部技术细节。对于非预期的错误（如非正常的请求、突破限制的请求等），应该简洁提示（如：系统错误）或不提示
- **你需要保证你说的内容和写的代码的正确性、真实性，对于没有把握、不知道的事情直接说出情况，不要猜测。你需要忠于事实**
- 使用无状态的函数式编程，如果需要使用类，请思考必要性并说明原因
- Python代码注意遵守类型安全，即使代码能够运行也要遵守类型检查器的约束要求
- 项目采用严格的分层架构，必须遵守单向依赖规则：上层可依赖下层，下层禁止依赖上层
- 使用英文注释，使用中文回复用户和交流
- 简单至上 (KISS): 追求代码和设计的极致简洁与直观，避免不必要的复杂性。
- 精益求精 (YAGNI): 仅实现当前明确所需的功能，抵制过度设计和不必要的未来特性预留。
- 坚实基础 (SOLID):
  - S (单一职责): 各组件、类、函数只承担一项明确职责。
  - O (开放/封闭): 功能扩展无需修改现有代码。
  - L (里氏替换): 子类型可无缝替换其基类型。
  - I (接口隔离): 接口应专一，避免“胖接口”。
  - D (依赖倒置): 依赖抽象而非具体实现。

## 实施的步骤

### 1. 项目理解

- 通过MCP、项目文档、项目代码、脚本等全面掌握其当前架构、核心组件、业务逻辑及痛点
- 在理解的基础上，初步识别项目中潜在的KISS, YAGNI, SOLID原则应用点或违背现象

### 2. 需求思考

- 用户并不专业，用户可能会了解或说出错误的内容。始终尊重事实。考虑用户提出的需求或想法是否合理，是否符合最佳实践、软件设计原则、项目要求、文档设计等，不要被用户的想法引导，如果违反原则或解决方案不优请直接指出
- 英文是否有拼写、语法错误
- 检查是否存在信息不完整或需要澄清、前后矛盾等问题，如果有不清楚的即刻提问而不是去猜测
- 对于做不到的要求、任务，不要勉强尝试，直接说明情况

### 3. 方案规划

- 在规划解决方案时，优先考虑如何通过应用上述原则，实现更简洁、高效和可扩展的改进，而非盲目增加功能
- 检查原本的实施情况是否存在架构设计不合理、代码冗余、存在死代码等问题，如果发现问题先报告。问题解决具备实施条件再继续
- 基于用户需求和对现有项目的理解，清晰定义本次迭代的具体任务范围和可衡量的预期成果
- 计划新建文件/函数前请充分检查类似的文件/函数是否已经存在
- **禁止**盲目重写已有功能而不理解上下文。**禁止**只关注局部问题而忽略对其他模块的影响。
- **你不得使用任何已不推荐、过时、或在未来版本可能被移除的 API，禁用过时 API / Deprecated 写法**，例如：
  - 禁止：Python 废弃的写法如datetime.utcnow()
  - 禁止：Pydantic v2已被移除的写法如min_items, max_items等
- 禁止使用 Python 黑魔法技巧，例如：动态修改模块、使用 getattr 拦截属性、运行时注入变量、猴子补丁（monkey patch）、隐式全局状态、隐式 lazy loading 等。所有代码必须采用清晰、显式、可维护的写法。
- 禁止在模块顶层（import 阶段）直接实例化应用对象、配置对象、数据库连接、客户端实例或其他可能带来副作用的实体。
  包括但不限于在模块顶部执行：db = SessionLocal(), engine = create_engine(db_url), client = OpenAI(api_key=...) 等。这些对象必须通过**显式函数**创建，例如工厂函数（如 create_app()）、依赖注入函数、或 @lru_cache() 包装的加载函数。
- 不允许未使用的变量或导入
- 遵循 PEP8 要求

### 4. 等待批准

将内容报告给用户，等待用户批准或与用户持续讨论调整和细化方案

### 5. 实施过程

- 用户批准后，开始实施。如果是持续修改同一个需求或问题，可不用频繁报告，但是需要简略说明发现的问题或接下来修改的内容再开始实施
- 如果修改过程中出现问题，如发现实施与预期或文档不符合、需要用户澄清或提供细节、实施出现分歧、无法获取信息、发现代码问题或完成某项操作（MCP调用失败、命令执行失败等）等情况，立即停止编码，并报告用户，请求用户提供更多信息

### 6. 检查和测试

- 修改后必须运行验证(见“必要检查”章节), 确保代码符合规范，Docker 必须正常运行，检查通过前不得报告"完成"
- 禁止跳过失败的检查

### 7. 文档和测试更新

- 如果增加了新功能或重大功能重构，需要增加或更新的测试内容
- 如果修改涉及到功能、接口、配置等变更，或者用户重新解释或者修改了设计与文档存在不同，必须同时更新 docs/*.md 相关文档
- 如果新发现或从用户处得到新的要求或流程，有必要持久化记录的，使用简洁的语言更新到相关目录下的 AGENTS.md (没有可以新建)
- 本文件需要更新的，则更新并使用简洁语言
- 如果有数据库修改，同步更新 backend/database/init/*.sql 文件和 docs/prototype/database.md 文档
- 文档更新必须找到正确的位置插入，并去除冗余和过时内容，而不是简单追加

## 实施的规范

### 注释规范

- 使用明确、无歧义的变量名、函数名与类名。仅为复杂算法、业务逻辑或特定技术决策添加注释。
- 注释应当避免的内容：
  - 写元注释，例如 `// Fix bug XX` 或 `// per request changed`
  - 写重复代码行为的注释，如 `// Increment i by 1`
  - 在最终提交中保留大块注释掉的旧代码。
- 修改的同时更新注释，同时精简过时和冗余注释

### 必要检查 (Python文件)

**代码修改后，必须执行以下检查流程，全部通过后才能报告"完成"。**

- 如果任何检查失败，必须立即修复，不得报告"已完成"
- 如果无法修复或不确定如何修复，立即停止工作并向用户说明情况
- 不得使用临时方案（如局部 import、type: ignore）绕过检查

#### 1. 语法检查（最基础，必须通过）

```bash
python -m py_compile backend/app/<修改的文件>.py
```

#### 2. Import 规范检查（必须通过）

```bash
python scripts/check_local_imports.py backend/app/<修改的文件>.py
```

优先使用相对导入，合理和必要使用 TYPE_CHECKING

#### 3. 代码格式化（自动修复）

```bash
# 自动格式化代码
black backend/app/<修改的文件>.py --config pyproject.toml

# 自动排序 imports
isort backend/app/<修改的文件>.py --settings-path pyproject.toml
```

#### 4. 类型安全检查（必须通过）

```bash
mypy backend/app/<修改的文件>.py --config-file pyproject.toml
```

添加正确的类型注解，或修复类型不匹配的代码
(当前系统尚存大量问题，需要逐步清理，但新修改的代码必须完全通过)

#### 5. 代码质量检查（必须通过）

```bash
pylint backend/app/<修改的文件>.py --rcfile pyproject.toml
```

逐个修复所有问题，确保 score ≥ 8.0
(当前系统尚存大量问题，需要逐步清理，但新修改的代码必须完全通过)

#### 6. 架构契约检查（如果修改了 services/ai 目录）

```bash
cd backend && lint-imports
```

调整 import，确保单向依赖（上层→下层）
如果发现循环导入问题，重构代码结构，调整模块依赖关系

#### 快速验证命令

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

## MCP

### Serena（本地代码分析优先）

**工具能力**：find_symbol, find_referencing_symbols, get_symbols_overview, search_for_pattern, read_file, replace_symbol_body, create_text_file, execute_shell_command
**触发场景**：代码检索、架构分析、跨文件引用、项目理解
**调用策略**：

- 先用 get_symbols_overview 快速了解文件结构
- find_symbol 精确定位（支持 name_path 模式匹配）
- search_for_pattern 用于复杂正则搜索
- 限制 relative_path 到相关目录，避免全项目扫描

### Code Index (代码索引)

**触发场景**：需要理解项目、代码审查、快速查找函数定义、分析代码依赖关系等场景

### Sequential Thinking（复杂规划）

**触发场景**：多步骤任务分解、架构设计、问题诊断流程
**输出要求**：6-10 步可执行计划，不暴露推理过程
**参数控制**：total_thoughts≤10, 每步一句话描述

### DuckDuckGo（外部信息）

**触发场景**：最新信息、官方公告、breaking changes
**查询优化**：≤12 关键词 + 限定词（site:, after:, filetype:）
**结果控制**：≤35 条，优先官方域名，过滤内容农场

### Chrome devtools（浏览器自动化）

**触发场景**：网页截图、表单测试、SPA 交互验证
**安全限制**：仅开发测试用途

### 其他 MCP

除了上述MCP以外可能还有其他的MCP可供使用, 可根据情况进行使用
