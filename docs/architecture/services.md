# 服务架构说明

## 微服务概览

### 服务列表

- **accounts_service** (端口 8001): 账号管理服务
- **contacts_service** (端口 8002): 联系人管理服务  
- **bot_message_service** (端口 8003): 消息处理服务
- **frontend** (端口 5173): Web前端应用

### 技术栈

- **后端**: Python + FastAPI + SQLAlchemy + MySQL
- **前端**: Vue 3 + Vite + Pinia + Vue Router
- **容器**: Docker + Docker Compose
- **消息**: LeanCloud IM + 事件总线

## 服务详细说明

### accounts_service (账号服务)

**职责范围**:

- 用户注册、登录、认证
- 短信验证码发送和验证
- JWT Token 生成和验证
- 用户基础信息管理
- 密码重置功能

**核心功能**:

```
认证管理 → JWT Token → 其他服务验证
短信服务 → 验证码 → 用户验证
用户管理 → 基础信息 → 账号状态
```

**数据管理**:

- users 表：用户账号基础信息
- 不涉及社交档案和联系人数据

### contacts_service (联系人服务)

**职责范围**:

- 用户联系人列表管理
- 社交档案信息管理
- LeanCloud系统对话管理
- 机器人模板和映射管理

**核心功能**:

```
联系人管理 → 关系维护 → 聊天列表
社交档案 → 显示信息 → 用户体验
对话映射 → LeanCloud ID → 消息路由
模板管理 → 机器人发现 → 联系人添加
```

**数据管理**:

- social_profiles 表：统一社交档案
- contacts 表：联系人关系
- conversation_mappings 表：对话ID映射
- template_mappings, bot_templates 表：模板管理

### bot_message_service (消息服务)

**职责范围**:

- LeanCloud webhook消息接收
- AI模型调用和响应生成
- 消息历史存储和管理
- 情感系统和关系状态管理
- 事件驱动的消息路由

**核心功能**:

```
消息接收 → Webhook → 事件总线
消息路由 → AI模型 → 响应生成
情感系统 → 关系发展 → 个性化回复
消息存储 → 历史记录 → 上下文管理
```

**数据管理**:

- bots 表：机器人配置信息
- message_history 表：消息历史
- emotions 表：情感状态跟踪

## 服务通信

### 内部认证

```
INTERNAL_SERVICE_KEY → 服务间调用认证
JWT Token → 用户身份验证
```

### API路由规则

```
/api/v1/system/* → bot_message_service:8003
/api/v1/contacts/* → contacts_service:8002
/api/v1/* → accounts_service:8001
```

### 事件总线

```python
# 消息事件流转
event_bus.publish("message_received", message_data)
event_bus.subscribe("message_processed", handle_response)
```

## 部署架构

### 开发环境

```yaml
# docker-compose.yml
services:
  accounts_service: 
    ports: ["8001:8000"]
  contacts_service:
    ports: ["8002:8000"] 
  bot_message_service:
    ports: ["8003:8000"]
  frontend:
    ports: ["5173:5173"]
  mysql:
    ports: ["3306:3306"]
```

### 生产环境

```yaml
# docker-compose.prod.yml
- 移除调试端口暴露
- 启用健康检查
- 配置资源限制
- 启用日志收集
```

### 稳定版本

```yaml
# docker-compose.stable.yml  
- 使用稳定镜像标签
- 严格的重启策略
- 完整的监控配置
```

## 设计原则

### 服务解耦

- 每个服务单一职责
- 数据库隔离，无共享表
- 通过API进行服务间通信
- 避免直接数据库访问

### 事件驱动

- 消息处理使用事件总线
- 异步处理提高性能
- 解耦消息发送和处理逻辑

### 无向后兼容

- MVP开发阶段，不考虑向后兼容
- 快速迭代，及时暴露问题
- 不使用默认值隐藏错误

### 函数式优先

- 配置和设置代码优先使用函数
- 避免不必要的类设计
- 简化代码结构和维护

## 扩展策略

### 水平扩展

- 服务无状态设计
- 支持多实例部署
- 负载均衡配置

### 垂直扩展

- 资源配置优化
- 数据库连接池调优
- 缓存策略优化

### 新服务添加

- 遵循现有API设计规范
- 使用统一的认证机制
- 集成事件总线通信
