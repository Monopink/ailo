# 后端开发规范

## 文档定位

本文件仅保留“必须遵守”的后端规则。
具体操作流程、命令清单、验收步骤统一以 Skills 为准，避免双份维护。

## 必读入口

- API 文档：`../docs/api/`
- 数据字典：`../docs/data-dict/`
- 迁移文档：`../docs/tech/MIGRATION.md`
- 参考资料：`../docs/references/`
- Admin 规则：`app/admin/AGENTS.md`（修改 `app/admin/` 前必读）

## 技术栈基线

- Python 3.12 + FastAPI
- PostgreSQL + SQLAlchemy Async + Alembic
- Pydantic v2
- Doubao（OpenAI SDK 兼容）
- Leancloud（仅消息传输）
- Starlette Admin（管理后台）

## 架构与依赖约束

分层依赖（上层可依赖下层，下层禁止反向依赖，同层禁止互相依赖）：

```
orchestrators
  -> relationship_scoring
  -> queries
  -> memory
  -> crud
  -> models
```

- 使用 `import-linter` 强制校验（配置：`.importlinter`）
- 能绝对导入时必须使用绝对导入
- Import 必须在文件顶部（`TYPE_CHECKING` 块除外）
- 禁止函数内部 import

## 关键实现规则

<critical-rules>

### 1) 异步 ORM 关系访问

- 异步上下文访问关系属性前，必须显式预加载（如 `selectinload`）
- 禁止依赖隐式 lazy load（建议模型关系使用 `lazy="raise"`）

### 2) 禁止模块顶层实例化

- 禁止在 import 阶段实例化数据库连接、外部客户端、配置加载器等副作用对象
- 使用依赖注入或工厂函数（可配合 `lru_cache`）进行延迟初始化

### 3) SQL 安全

- 默认禁止 f-string 拼接 SQL（S608）
- 必须使用参数化查询传递动态值
- 少量豁免需同时满足：代码注释说明安全性 + `pyproject.toml` 记录审查 + 不包含用户输入

### 4) API 错误响应规范

- 所有 HTTP 4xx/5xx 必须遵循 `docs/api/error-codes.md`
- 禁止暴露内部实现和第三方状态细节（配置、连接、服务异常等）

</critical-rules>

## 配置与数据边界

- 环境变量（`.env`）：安全敏感、稳定配置
- `system_configs`：可运营变更、非敏感配置
- Leancloud 仅用于消息传输，不承载业务状态
- 业务数据必须落 PostgreSQL

## 数据库变更同步

当 schema 发生变更，必须同步更新：

1. `backend/database/init/**/*.sql`
2. `docs/data-dict/*.md`

禁止以“手工改线上库”替代迁移。

## 编码规范

- 函数参数与返回值必须完整类型注解
- 业务层优先具体类型；`Any` 仅可出现在第三方框架交互边界，且需标注原因
- 外部输入优先用 Pydantic 模型校验
- 枚举分层：内部状态类枚举（status/type/result）使用数字；跨边界标识类枚举（如 client_type/locale）使用字符串
- 命名遵循 PEP8：`snake_case` / `PascalCase` / `UPPER_CASE`
- 优先无状态函数；若使用类需有明确理由
- 涉及时区/相对时间/人性化时间统一使用 `pendulum`

## 开发流程约束

- 修改后必须执行验证，失败不得报完成
- 禁止用临时方案掩盖问题（例如无理由 `type: ignore`、兼容回退）
- 后端验证流程请使用：`/validate`
- 数据库迁移与同步请使用：`/database migrate`
- 提交前总检查请使用：`/pre-commit-check`

## 测试约定

- 测试文件命名: `test_<模块名>.py`
- 测试函数命名: `test_<功能描述>`
- 可用 fixtures: `db_session`, `client`, `auth_headers`
