# 服务架构说明

## 后端架构概览

### 服务列表

- **backend** (端口 8000): 后端服务
- **web_frontend** (端口 5173): Web前端应用

### 技术栈

- **后端**: Python + FastAPI + SQLAlchemy + MySQL
- **前端**: Vue 3 + Vite + Pinia + Vue Router
- **容器**: Docker + Docker Compose
- **消息**: LeanCloud IM + 事件总线

## 后端服务详细说明

### service (后端服务)

**职责范围**:

- 用户注册、登录、认证
- 短信验证码发送和验证
- JWT Token 生成和验证
- 用户基础信息管理
- 密码重置功能
- 用户联系人列表管理
- 社交档案信息管理
- LeanCloud系统对话管理
- 机器人模板和映射管理
- LeanCloud webhook消息接收
- AI模型调用和响应生成
- 消息历史存储和管理
- 情感系统和关系状态管理
- 事件驱动的消息路由

**核心功能**:

```text
认证管理 → JWT Token → 用户验证
短信服务 → 验证码 → 用户验证
用户管理 → 基础信息 → 账号状态
联系人管理 → 关系维护 → 聊天列表
社交档案 → 显示信息 → 用户体验
对话映射 → LeanCloud ID → 消息路由
模板管理 → 机器人发现 → 联系人添加
消息接收 → Webhook → 事件总线
消息路由 → AI模型 → 响应生成
情感系统 → 关系发展 → 个性化回复
消息存储 → 历史记录 → 上下文管理
用户资料 → 变化检测 → 个性化交互
```

**数据管理**:

- users 表：用户账号基础信息
- social_profiles 表：统一社交档案
- contacts 表：联系人关系
- conversation_mappings 表：对话ID映射
- template_mappings, bot_templates 表：模板管理
- bots 表：机器人配置信息
- message_history 表：消息历史
- emotions 表：情感状态跟踪

## 服务通信

### 内部认证

```text
JWT Token → 用户身份验证
内部模块直接调用 → 无需服务间认证
```

### API路由规则

```text
/api/v1/* → service:8000
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
  service:
    ports: ["8000:8000"]
  web:
    ports: ["5173:5173"]
  mysql:
    ports: ["33061:3306"]
```

### 生产环境

```yaml
# docker-compose.prod.yml
- 移除调试端口暴露
- 启用健康检查
- 配置资源限制
- 启用日志收集
- 单一后端服务部署
```

### 稳定版本

```yaml
# docker-compose.stable.yml
- 使用稳定镜像标签
- 严格的重启策略
- 完整的监控配置
- 统一服务监控
```

## 设计原则

### 模块化设计

- 每个模块单一职责
- 统一数据库，模块间直接调用
- 保持原有代码结构和逻辑
- 减少服务间通信开销

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

### 新功能添加

- 遵循现有API设计规范
- 使用统一的认证机制
- 集成事件总线通信
- 保持模块化结构
