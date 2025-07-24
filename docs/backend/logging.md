# 日志配置和管理

## 概述

后端服务使用结构化日志系统，基于structlog库实现JSON格式日志输出，便于日志分析和监控。

## 日志级别配置

### 环境变量控制

```bash
# 数据库SQL查询日志（开发环境建议开启，生产环境建议关闭）
DB_ECHO=false

# 应用日志级别
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR, CRITICAL
```

### 开发环境配置

```bash
# .env.development
DB_ECHO=true
LOG_LEVEL=DEBUG
```

### 生产环境配置

```bash
# .env.production
DB_ECHO=false
LOG_LEVEL=INFO
```

### 测试环境配置

```bash
# .env.testing
DB_ECHO=false
LOG_LEVEL=WARNING
```

## 日志输出位置

### 文件日志

- **位置**: `/app/logs/service.log`
- **格式**: JSON结构化日志
- **级别**: DEBUG及以上

### 控制台日志

- **输出**: 标准输出(stdout)
- **格式**: JSON结构化日志
- **级别**: INFO及以上

## 日志内容控制

### 数据库日志优化

**问题**: 数据库echo=True会产生大量SQL查询日志

**解决方案**:

```python
# 在backend/app/core/database.py中已实现
echo_sql = getattr(settings, 'DB_ECHO', False)
engine = create_async_engine(settings.database_url, echo=echo_sql, ...)
```

**使用方式**:

- 开发调试时: `DB_ECHO=true`
- 生产环境: `DB_ECHO=false` (默认)

### 应用日志级别调整

**修改方式**:

1. 环境变量: `LOG_LEVEL=WARNING`
2. 代码中动态调整:

```python
import logging
logging.getLogger().setLevel(logging.WARNING)
```

## 敏感信息保护

### 自动过滤规则

- 密码字段自动脱敏
- JWT token只记录前20字符
- 手机号脱敏显示: `138****5678`

### 安全日志实践

```python
# ✅ 正确的日志记录
logger.info("user_login_success", user_id=user.entity_id)

# ❌ 避免记录敏感信息
logger.info("user_login", password=password)  # 不要这样做
```

## 日志监控和分析

### 日志格式示例

```json
{
  "event": "user_login_success",
  "level": "info",
  "timestamp": "2024-07-22T10:30:00.123456Z",
  "logger": "backend.app.api.v1.client.auth",
  "module": "auth",
  "func_name": "login_with_password",
  "lineno": 95,
  "user_id": "qqid_u123456"
}
```

### 关键监控指标

- 错误率: `level=error` 的日志数量
- 响应时间: 包含 `execution_time_ms` 的日志
- 数据库连接: `database_connection_*` 事件
- 认证失败: `jwt_token_*` 相关错误

## 生产环境优化建议

### 日志轮转

```bash
# 使用logrotate配置日志轮转
/app/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 644 appuser appuser
}
```

### 性能优化

1. **减少日志级别**: 生产环境使用INFO或WARNING
2. **关闭SQL日志**: `DB_ECHO=false`
3. **异步日志**: 考虑使用异步日志处理器

### 监控集成

- **ELK Stack**: Elasticsearch + Logstash + Kibana
- **Prometheus**: 基于日志指标的监控
- **Grafana**: 日志可视化面板

## 故障排查

### 常见问题

**1. 日志文件过大**

```bash
# 检查日志文件大小
du -h /app/logs/service.log

# 临时解决: 清空日志文件
> /app/logs/service.log
```

**2. 数据库日志过多**

```bash
# 关闭数据库日志
export DB_ECHO=false
# 重启服务
```

**3. 日志级别调整不生效**

```bash
# 检查环境变量
echo $LOG_LEVEL

# 重启容器使配置生效
docker-compose restart service
```

### 调试模式

```bash
# 临时开启详细日志
export DB_ECHO=true
export LOG_LEVEL=DEBUG

# 重启服务
docker-compose restart service
```

## 最佳实践

1. **开发环境**: 开启详细日志便于调试
2. **生产环境**: 关闭冗余日志，关注错误和关键事件
3. **定期清理**: 设置日志轮转和清理策略
4. **监控告警**: 基于错误日志设置告警机制
5. **安全审计**: 记录关键操作但保护敏感信息
