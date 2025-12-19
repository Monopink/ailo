# 数据库迁移系统使用指南

本项目使用 Alembic 作为唯一的数据库迁移管理工具。所有数据库结构变更必须通过 Alembic 迁移脚本进行。

## 🎯 快速开始

### 1. 环境准备

确保已安装必要的Python包：
```bash
pip install alembic psycopg2-binary sqlalchemy pydantic pydantic-settings
```

### 2. 基本命令（容器内执行）

确保 `docker compose -f deployment/docker-compose.yml up backend` 已启动并健康，然后在宿主机执行：

```bash
# 查看当前迁移状态
docker exec backend_container alembic current

# 查看迁移历史
docker exec backend_container alembic history --verbose

# 应用所有待执行的迁移
docker exec backend_container alembic upgrade head

# 生成新的迁移脚本（自动生成）
docker exec backend_container alembic revision --autogenerate -m "描述变更内容"
```

## 📁 目录结构

```
backend/
├── alembic/                   # Alembic 迁移目录
│   ├── versions/              # 迁移脚本目录
│   ├── env.py                 # Alembic 环境配置
│   └── script.py.mako         # 迁移脚本模板
├── alembic.ini                # Alembic 配置文件
├── app/                       # 应用代码目录
│   └── ...                    # 其他应用代码
└── README_MIGRATION.md        # 本文档
```

## 🔧 配置说明

### 环境变量配置

迁移使用统一的 `.env`（与服务共用），容器内 `alembic` 自动读取：

```bash
# PostgreSQL 连接设置
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DATABASE=ailo_db
POSTGRES_USER=user
POSTGRES_PASSWORD=password
```

### 异步 vs 同步连接

- **应用运行时**: 使用异步连接 (`postgresql+asyncpg://`) 获得更好性能
- **数据库迁移时**: 使用同步连接 (`postgresql://`) 确保 Alembic 正常工作
- **自动转换**: `env.py` 会自动将异步URL转换为同步URL

## 📋 完整命令列表

### 直接使用 Alembic（推荐）

```bash
docker exec backend_container alembic current                 # 显示当前版本
docker exec backend_container alembic history --verbose       # 详细历史
docker exec backend_container alembic upgrade head            # 升级到最新
docker exec backend_container alembic downgrade -1            # 降级一个版本
docker exec backend_container alembic revision --autogenerate -m "消息"  # 生成迁移
```

## 🔄 开发工作流程

### 当前阶段（开发环境）

1. **修改模型**: 在 `app/models/` 中修改 SQLAlchemy 模型
2. **生成迁移**: `docker exec backend_container alembic revision --autogenerate -m "描述变更"`
3. **审查迁移脚本**: 检查 `backend/alembic/versions/` 下生成的文件
4. **应用迁移**: `docker exec backend_container alembic upgrade head`
5. **测试验证**: 确保数据库结构正确

### 示例工作流程

```bash
# 1. 修改模型后生成迁移
docker exec backend_container alembic revision --autogenerate -m "Add user avatar field"

# 2. 查看生成的迁移文件
# 检查 backend/alembic/versions/ 目录下的新文件

# 3. 应用迁移
docker exec backend_container alembic upgrade head

# 4. 验证当前状态
docker exec backend_container alembic current
```

## ⚠️ 注意事项

### 开发环境

1. **备份数据**: 重要数据请先备份
2. **审查脚本**: 自动生成的迁移脚本需要人工审查
3. **测试迁移**: 在开发环境充分测试后再部署

### 生产环境

1. **停机维护**: 重要的结构变更需要停机维护
2. **备份数据库**: 执行迁移前务必备份数据库
3. **回滚准备**: 准备回滚方案和脚本

### 团队协作

1. **版本控制**: 迁移脚本必须提交到版本控制系统
2. **同步迁移**: 团队成员需要及时同步和应用迁移
3. **冲突解决**: 多人开发时注意迁移版本冲突

## 🐛 故障排除

### 常见问题

1. **连接失败**: 检查 `.env.migration` 中的数据库配置
2. **模型导入失败**: 检查 `env.py` 中的路径配置
3. **版本冲突**: 多人开发时的迁移版本冲突

### 解决方案

```bash
# 检查迁移状态
python migrate.py check

# 查看详细错误信息
alembic upgrade head --sql

# 强制标记当前状态（谨慎使用）
alembic stamp head
```

## 🎯 最佳实践

1. **描述性消息**: 迁移消息要清晰描述变更内容
2. **小步迁移**: 避免在单个迁移中进行过多变更
3. **可回退性**: 确保迁移可以安全回退
4. **数据迁移**: 结构变更和数据迁移分开处理
5. **索引管理**: 大表的索引操作要特别小心

## 📚 相关资源

- [Alembic 官方文档](https://alembic.sqlalchemy.org/)
- [SQLAlchemy 文档](https://docs.sqlalchemy.org/)
- [PostgreSQL 文档](https://www.postgresql.org/docs/)
