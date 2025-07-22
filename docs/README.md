# 项目文档

## 文档结构

### API接口文档 (`/api`)

- **[backend.md](api/backend.md)** - 后端API接口
- **[formats.md](api/formats.md)** - 数据格式规范

### 数据库设计 (`/database`)

- **[schema.md](database/schema.md)** - 数据库表结构设计
- **[relationships.md](database/relationships.md)** - 数据关系说明

### 系统架构 (`/architecture`)

- **[services.md](architecture/services.md)** - 后端架构说明
- **[message-flow.md](architecture/message-flow.md)** - 消息处理流程
- **[security.md](architecture/security.md)** - 安全设计规范

### 前端开发 (`/frontend`)

- **[components.md](frontend/components.md)** - 组件设计规范
- **[state-management.md](frontend/state-management.md)** - 状态管理说明
- **[ui-standards.md](frontend/ui-standards.md)** - UI设计标准

## 核心技术信息

### 服务端口

- backend (后端): 8000
- web_frontend: 5173

### 主要技术栈

- **后端**: Python + FastAPI + SQLAlchemy + MySQL
- **前端**: Vue 3 + Vite + Pinia + Vue Router
- **消息**: LeanCloud IM + 事件总线
- **容器**: Docker + Docker Compose

### Entity ID 格式

- 格式: `qqid_{type}{number}`
- 用户: `qqid_u1001`
- 机器人: `qqid_b9001`
- 系统: `qqid_s1001`

### 核心数据表

- **users** - 用户账号信息
- **bots** - AI机器人配置
- **social_profiles** - 统一社交档案
- **contacts** - 联系人关系
- **message_history** - 消息历史
- **emotions** - 情感状态

### 消息类型枚举

- `1`: CHAT - 普通聊天消息
- `2`: TYPING - 输入状态指示  
- `9`: SYSTEM - 系统通知消息

### 联系人类型

- `1`: 普通用户
- `2`: AI机器人

## 设计原则

### 服务设计

- **单一职责**: 每个服务专注特定功能
- **事件驱动**: 使用事件总线解耦消息处理
- **无向后兼容**: MVP阶段，快速迭代

### API设计

- **无ID暴露**: 不暴露数据库自增ID
- **统一格式**: 使用entity_id作为业务主键
- **错误透明**: 不使用默认值隐藏错误
- **JWT认证**: 无状态认证机制

### 前端设计

- **现代UI**: macOS/Notion风格，大圆角设计
- **绿色主色**: #42db5a 主色，#fdd700 强调色
- **无回退机制**: 不使用默认值，明确显示数据状态
- **响应式**: 支持桌面和移动端

### 数据库设计

- **无外键**: 避免服务间数据库耦合
- **字符串ID**: 全局唯一的entity_id系统
- **JSON配置**: 灵活的配置字段设计
- **应用层约束**: 通过代码逻辑管理数据关系

## 消息处理流程

```text
用户发送消息 → LeanCloud IM → Webhook → backend
                                              ↓
                                         event_bus
                                              ↓
                                      message_router
                                              ↓
                                        AI模型处理
                                              ↓
                                         响应生成
                                              ↓
                                    LeanCloud API发送
```

## 开发环境

### 启动命令

```bash
# 开发环境
./start.sh
docker-compose up -d

# 生产环境  
docker-compose -f docker-compose.prod.yml up -d

# 稳定版本
docker-compose -f docker-compose.stable.yml up -d
```

### 访问地址

- Web前端: <http://localhost:5173>
- 日志查看: <http://localhost:9999>
- ngrok管理: <http://localhost:4040>

### 测试账号

- 手机号: 13800138002
- 密码: 12345678
- 验证码: 任意6位数字（开发环境）

## 文档维护

### 更新原则

- 保持内容简洁，专注技术要点
- 及时更新API变更和数据结构变化
- 移除过时和无关内容
- 使用中文，面向开发者

### 文档分类

- **API文档**: 接口规范和数据格式
- **架构文档**: 系统设计和处理流程
- **数据库文档**: 表结构和关系设计
- **前端文档**: 组件设计和UI规范

这些文档专为内部开发团队设计，包含项目的核心技术信息，便于开发者快速查阅和理解系统设计。
