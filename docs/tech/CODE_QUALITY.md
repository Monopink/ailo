# 代码质量检查命令

## 后端检查 (Python)

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

## 前端检查 (TypeScript)

### 完整检查

```bash
cd frontend/wx-minipg
npm run check  # 必须通过
```

### 单独工具

```bash
# TypeScript 类型检查（必须通过）
npm run type-check

# ESLint 检查
npm run lint
npm run lint:fix  # 自动修复

# 代码格式化（自动修复）
npm run format
npm run format:check  # 仅检查不修复
```

## 提交前必须执行

**后端**:
```bash
./scripts/validate.sh --quick
```

**前端**:
```bash
cd frontend/wx-minipg && npm run check
```

## 工具配置文件

**后端**:
- `pyproject.toml` - ruff, mypy 配置
- `.importlinter` - 架构契约配置
- `.pre-commit-config.yaml` - Git hooks 配置

**前端**:
- `tsconfig.json` - TypeScript 配置
- `.eslintrc.json` - ESLint 配置
- `.prettierrc.json` - Prettier 配置

## 检查失败处理

- 语法错误: 修复代码语法
- Import 位置错误: 移动 import 到文件顶部
- 类型错误: 添加类型注解或修复类型不匹配
- 架构违规: 调整 import，确保单向依赖（上层→下层）
- 代码质量问题: 逐个修复 ruff/ESLint 报告的问题

**禁止**:
- 跳过检查 (`git commit --no-verify`)
- 使用临时方案绕过检查 (`type: ignore`, `# noqa`)
