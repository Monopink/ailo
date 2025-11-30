# 代码质量工具使用指南

## 概述

本项目使用多层代码质量保障体系，确保代码规范、类型安全和架构一致性。

## 工具列表

| 工具 | 用途 | 配置文件 |
|------|------|----------|
| **black** | 代码格式化 | pyproject.toml |
| **isort** | Import 排序 | pyproject.toml |
| **mypy** | 类型检查 | pyproject.toml |
| **pylint** | 代码质量检查 | pyproject.toml |
| **import-linter** | 架构契约检查 | .importlinter |
| **pre-commit** | Git 提交前自动检查 | .pre-commit-config.yaml |

## 快速开始

### 1. 安装工具

```bash
# 安装所有开发工具
pip install -r backend/app/requirements.txt

# 安装 pre-commit hooks
pre-commit install
```

### 2. 日常使用

#### 修改代码后的检查流程

```bash
# 1. 自动格式化代码
black backend/app/<修改的文件>.py --config pyproject.toml
isort backend/app/<修改的文件>.py --settings-path pyproject.toml

# 2. 类型检查
mypy backend/app/<修改的文件>.py --config-file pyproject.toml

# 3. 代码质量检查
pylint backend/app/<修改的文件>.py --rcfile pyproject.toml

# 4. 架构契约检查（如果修改了 services/ai 目录）
cd backend && lint-imports
```

#### 快速验证脚本

```bash
# 只检查 git 修改的文件（推荐）
./scripts/validate.sh --quick

# 检查所有文件
./scripts/validate.sh
```

### 3. Git 提交

配置了 pre-commit hooks 后，每次 `git commit` 会自动运行检查：

```bash
git add .
git commit -m "Your commit message"
# pre-commit 会自动运行所有检查
```

如果检查失败，提交会被阻止。修复问题后重新提交。

## 工具详解

### Black - 代码格式化

**用途**：统一代码风格，自动格式化代码

**配置**：
- 行长：108 字符
- 目标版本：Python 3.12
- 排除：migrations, venv, __pycache__

**使用**：
```bash
# 检查格式
black --check backend/app --config pyproject.toml

# 自动格式化
black backend/app --config pyproject.toml
```

### isort - Import 排序

**用途**：自动排序和分组 import 语句

**配置**：
- 兼容 black
- 行长：108 字符
- 分组：FUTURE, STDLIB, THIRDPARTY, FIRSTPARTY, LOCALFOLDER

**使用**：
```bash
# 检查排序
isort --check-only backend/app --settings-path pyproject.toml

# 自动排序
isort backend/app --settings-path pyproject.toml
```

### mypy - 类型检查

**用途**：静态类型检查，确保类型安全

**配置**：
- Python 版本：3.12
- 检查未类型化的定义：否（渐进式启用）
- 严格相等性检查：是

**使用**：
```bash
# 检查单个文件
mypy backend/app/main.py --config-file pyproject.toml

# 检查整个目录
mypy backend/app --config-file pyproject.toml
```

**常见错误**：
- `union-attr`: 可能为 None 的对象调用方法 → 添加 None 检查
- `arg-type`: 参数类型不匹配 → 修正类型注解
- `no-any-return`: 返回 Any 类型 → 添加具体类型注解

### pylint - 代码质量检查

**用途**：检查代码规范、潜在错误、代码异味

**配置**：
- 最大行长：108
- 命名规范：PEP8
- 禁用：fixme, too-few-public-methods, missing-docstring（MVP 阶段）

**使用**：
```bash
# 检查单个文件
pylint backend/app/main.py --rcfile pyproject.toml

# 检查整个目录
pylint backend/app --rcfile pyproject.toml

# 不显示分数
pylint backend/app --rcfile pyproject.toml --score=no
```

**评分标准**：
- 10.0：完美
- ≥ 8.0：良好（最低要求）
- < 8.0：需要改进

### import-linter - 架构契约检查

**用途**：强制执行分层架构，防止循环依赖

**配置**：
- 根包：app
- 契约类型：layers（分层架构）
- 层级：orchestrators → relationship_scoring → conversation_memory → ...

**使用**：
```bash
# 检查架构契约
cd backend && lint-imports

# 或使用包装脚本（Windows 兼容）
python scripts/run_import_linter.py
```

**架构规则**：
- 上层可以依赖下层
- 下层不能依赖上层
- 同层之间不能相互依赖

### check_local_imports - Import 位置检查

**用途**：确保所有 import 在文件顶部，不在函数内部

**使用**：
```bash
# 检查单个文件
python scripts/check_local_imports.py backend/app/main.py

# 检查整个目录
python scripts/check_local_imports.py backend/app
```

**例外**：
- `TYPE_CHECKING` 块内的 import 允许在任何位置

## 常见问题

### Q1: 如何临时跳过 pre-commit 检查？

```bash
# 仅紧急情况，需用户明确批准
git commit --no-verify
```

### Q2: 如何修复格式化问题？

```bash
# 自动修复格式化和 import 排序
black backend/app --config pyproject.toml
isort backend/app --settings-path pyproject.toml
```

### Q3: mypy 报告太多错误怎么办？

渐进式修复：
1. 先修复明显的类型错误
2. 添加类型注解到函数签名
3. 处理 None 检查
4. 逐步启用更严格的检查

### Q4: pylint 分数低于 8.0 怎么办？

1. 查看具体错误信息
2. 逐个修复问题
3. 如果是误报，考虑在 pyproject.toml 中禁用该规则
4. 不要使用 `# pylint: disable` 注释（除非必要）

### Q5: import-linter 报告架构违规怎么办？

1. 检查 import 语句
2. 确保遵守分层架构：上层 → 下层
3. 如果需要跨层通信，考虑重构
4. 更新 .importlinter 配置（如果架构设计变更）

### Q6: Windows 下 import-linter 编码错误？

使用包装脚本：
```bash
python scripts/run_import_linter.py
```

## 最佳实践

### 1. 开发流程

```
修改代码 → 自动格式化 → 类型检查 → 质量检查 → 架构检查 → Git 提交
```

### 2. 提交前检查

```bash
# 快速检查修改的文件
./scripts/validate.sh --quick

# 如果通过，提交
git add .
git commit -m "Your message"
```

### 3. 修复问题的优先级

1. **语法错误**（最高优先级）
2. **Import 位置错误**
3. **类型错误**
4. **架构违规**
5. **代码质量问题**

### 4. 类型注解建议

```python
# 好的类型注解
def get_user(user_id: int) -> User | None:
    """Get user by ID."""
    return db.query(User).filter(User.id == user_id).first()

# 避免使用 Any
def process_data(data: Any) -> Any:  # 不好
    pass

def process_data(data: dict[str, str]) -> list[str]:  # 好
    pass
```

### 5. Import 组织

```python
# 标准库
import os
import sys
from typing import TYPE_CHECKING

# 第三方库
from fastapi import FastAPI
from pydantic import BaseModel

# 本地模块
from app.core.config import settings
from app.models.user import User

# TYPE_CHECKING 块（避免循环导入）
if TYPE_CHECKING:
    from app.services.ai import AIService
```

## 持续改进

### 渐进式启用严格检查

当代码质量提升后，可以在 pyproject.toml 中启用更严格的检查：

```toml
[tool.mypy]
disallow_untyped_defs = true  # 要求所有函数有类型注解
disallow_incomplete_defs = true  # 要求完整的类型注解
```

### 定期全面检查

```bash
# 每周运行一次全面检查
./scripts/validate.sh

# 查看 pylint 报告
pylint backend/app --rcfile pyproject.toml --output-format=json > pylint_report.json
```

## 故障排除

### 工具未安装

```bash
pip install -r backend/app/requirements.txt
```

### pre-commit hooks 未生效

```bash
pre-commit install
pre-commit run --all-files
```

### 配置文件找不到

确保在项目根目录运行命令，或使用绝对路径。

## 参考资源

- [Black 文档](https://black.readthedocs.io/)
- [isort 文档](https://pycqa.github.io/isort/)
- [mypy 文档](https://mypy.readthedocs.io/)
- [pylint 文档](https://pylint.readthedocs.io/)
- [import-linter 文档](https://import-linter.readthedocs.io/)
- [pre-commit 文档](https://pre-commit.com/)
