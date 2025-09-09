# 后端文件目录结构设计

## 完整目录结构

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                     # FastAPI应用入口
│   ├── requirements.txt            # Python依赖
│   ├── Dockerfile                  # Docker配置
│   ├── Dockerfile.prod            # 生产环境Docker配置
│   │
│   ├── api/                        # API路由层
│   │   ├── __init__.py
│   │   ├── deps.py                 # 依赖注入
│   │   └── v1/                     # API版本1
│   │       ├── __init__.py
│   │       ├── auth.py             # 认证相关API
│   │       ├── users.py            # 用户管理API
│   │       ├── contacts.py         # 联系人管理API
│   │       ├── square.py           # 广场功能API
│   │       ├── media.py            # 媒体文件API
│   │       ├── webhook.py          # LeanCloud Webhook接收
│   │       └── admin/              # 管理后台API
│   │           ├── __init__.py
│   │           ├── auth.py         # 管理员认证
│   │           ├── users.py        # 用户管理
│   │           ├── ai.py           # AI管理
│   │           ├── messages.py     # 消息管理
│   │           ├── security.py     # 安全监控
│   │           ├── media.py        # 媒体文件管理
│   │           └── system.py       # 系统管理
│   │
│   ├── services/                   # 业务服务层
│   │   ├── __init__.py
│   │   ├── auth.py                 # 认证服务
│   │   ├── user.py                 # 用户服务
│   │   ├── contact.py              # 联系人服务
│   │   ├── media.py                # 媒体文件服务
│   │   │
│   │   ├── message/                # 消息服务模块
│   │   │   ├── __init__.py
│   │   │   ├── core.py             # 消息服务核心逻辑
│   │   │   ├── buffer.py           # 消息合并缓冲器
│   │   │   ├── crypto.py           # 消息加解密
│   │   │   ├── signature.py        # 消息签名验证
│   │   │   ├── rate_limiter.py     # 消息频率限制
│   │   │   └── providers/          # 消息服务提供商
│   │   │       ├── __init__.py
│   │   │       ├── base.py         # 抽象基类
│   │   │       └── leancloud/      # LeanCloud实现
│   │   │           ├── __init__.py
│   │   │           ├── webhook.py  # Webhook处理
│   │   │           ├── sender.py   # 消息发送
│   │   │           └── client.py   # LeanCloud客户端
│   │   │
│   │   ├── ai/                     # AI服务模块
│   │   │   ├── __init__.py
│   │   │   ├── core.py             # AI服务核心逻辑
│   │   │   ├── context.py          # 对话上下文管理
│   │   │   ├── prompt.py           # 系统提示词构建
│   │   │   ├── character.py        # AI角色管理
│   │   │   ├── security.py         # 内容安全检测
│   │   │   ├── llm_client.py       # 大模型客户端
│   │   │   └── processors/         # 消息处理器
│   │   │       ├── __init__.py
│   │   │       ├── text.py         # 文本消息处理
│   │   │       └── system.py       # 系统消息处理
│   │   │
│   │   └── admin/                  # 管理后台服务
│   │       ├── __init__.py
│   │       ├── user.py             # 管理后台用户服务
│   │       ├── ai.py               # 管理后台AI服务
│   │       ├── message.py          # 管理后台消息服务
│   │       ├── security.py         # 管理后台安全服务
│   │       └── system.py           # 管理后台系统服务
│   │
│   ├── repositories/               # 数据访问层
│   │   ├── __init__.py
│   │   ├── base.py                 # 基础Repository类
│   │   ├── user.py                 # 用户数据访问
│   │   ├── contact.py              # 联系人数据访问
│   │   ├── message.py              # 消息数据访问
│   │   ├── ai.py                   # AI相关数据访问
│   │   ├── media.py                # 媒体文件数据访问
│   │   ├── security.py             # 安全相关数据访问
│   │   └── admin.py                # 管理员相关数据访问
│   │
│   ├── models/                     # 数据库模型
│   │   ├── __init__.py
│   │   ├── base.py                 # 基础模型类
│   │   ├── user.py                 # 用户相关表模型
│   │   ├── contact.py              # 联系人相关表模型
│   │   ├── message.py              # 消息相关表模型
│   │   ├── ai.py                   # AI相关表模型
│   │   ├── media.py                # 媒体文件表模型
│   │   ├── security.py             # 安全相关表模型
│   │   ├── admin.py                # 管理员相关表模型
│   │   └── system.py               # 系统相关表模型
│   │
│   ├── schemas/                    # Pydantic模型
│   │   ├── __init__.py
│   │   ├── common.py               # 通用模型
│   │   ├── auth.py                 # 认证相关模型
│   │   ├── user.py                 # 用户相关模型
│   │   ├── contact.py              # 联系人相关模型
│   │   ├── message.py              # 消息相关模型
│   │   ├── ai.py                   # AI相关模型
│   │   ├── media.py                # 媒体文件模型
│   │   └── admin.py                # 管理后台模型
│   │
│   ├── crud/                       # CRUD操作（如果需要）
│   │   ├── __init__.py
│   │   └── base.py                 # 基础CRUD类
│   │
│   ├── core/                       # 核心功能
│   │   ├── __init__.py
│   │   ├── config.py               # 配置管理
│   │   ├── security.py             # 安全相关（JWT等）
│   │   ├── auth.py                 # 认证逻辑
│   │   └── permissions.py          # 权限控制
│   │
│   ├── utils/                      # 工具函数
│   │   ├── __init__.py
│   │   ├── logging.py              # 日志工具（已存在）
│   │   ├── security.py             # 安全工具
│   │   ├── validators.py           # 验证工具
│   │   ├── formatters.py           # 格式化工具
│   │   ├── snowflake.py            # Snowflake ID生成器
│   │   ├── redis_client.py         # Redis客户端
│   │   ├── exceptions.py           # 自定义异常
│   │   └── helpers.py              # 辅助函数
│   │
│   └── admin/                      # 管理后台前端（如果需要）
│       └── [管理后台静态文件]
│
└── database/                       # 数据库相关
    ├── conf/                       # 数据库配置
    └── init/                       # 数据库初始化脚本
```

## 关键模块设计说明

### 1. 消息服务流程设计 (services/message/)

#### 核心流程

```
Webhook接收 → 消息验证 → 安全检测 → 消息缓冲 → AI处理 → 消息发送
```

#### 详细说明

- **core.py**: 消息服务主控制器，协调各个组件
- **buffer.py**: 短时间内消息合并，减少AI调用频次
- **crypto.py**: 消息内容加解密，保护用户隐私
- **signature.py**: 系统消息签名验证，防止伪造
- **rate_limiter.py**: 用户消息频率限制，防止刷屏
- **providers/**: 消息服务提供商抽象，支持LeanCloud等

### 2. AI服务流程设计 (services/ai/)

#### 核心流程

```
接收消息 → 角色识别 → 上下文构建 → 提示词生成 → LLM调用 → 响应处理
```

#### 详细说明

- **core.py**: AI服务主控制器
- **context.py**: 管理对话历史和上下文
- **prompt.py**: 根据角色和情况构建系统提示词
- **character.py**: AI角色管理和特征提取
- **security.py**: 内容安全检测，过滤违规内容
- **llm_client.py**: 大模型API客户端封装

### 3. 数据访问层设计 (repositories/)

#### 设计原则

- 每个业务领域一个Repository
- 继承base.py的基础CRUD操作
- 封装复杂查询逻辑
- 支持事务管理

### 4. API层设计 (api/v1/)

#### 设计原则

- RESTful API设计
- 统一的响应格式
- 完整的错误处理
- 管理后台API独立分组

## 配置管理设计

### 配置分层策略（符合最佳实践）

#### 第一层：代码默认值

- **用途**：应用基础配置、不敏感的默认值
- **示例**：应用名称、版本号、超时时间、重试次数
- **优点**：开发友好，无需额外配置即可运行

#### 第二层：环境变量/配置文件

- **用途**：敏感信息、环境相关配置
- **敏感信息**：数据库密码、API密钥、JWT密钥
- **环境配置**：数据库连接、Redis连接、外部服务URL、日志级别
- **支持**：环境变量和.env文件，环境变量优先级更高

#### 第三层：运行时配置（可选，后期扩展）

- **用途**：业务规则配置、功能开关
- **存储**：system_config表
- **示例**：联系人限制、消息长度限制、功能开关
- **优点**：可动态调整，无需重启应用

### 配置优先级

```
环境变量 > .env文件 > 代码默认值 > 数据库配置
```

### 配置实现原则

1. **敏感信息**：必须通过环境变量提供，无默认值
2. **环境相关**：提供合理默认值，支持环境变量覆盖
3. **业务配置**：代码默认值，后期可扩展到数据库
4. **开发友好**：最小配置即可启动开发环境

## 数据库迁移设计

### 开发阶段数据库管理原则

**重要：当前项目处于MVP开发阶段，采用以下原则：**

1. **不进行数据库迁移操作** - 开发阶段不使用Alembic迁移，避免复杂的版本管理
2. **直接修改初始化文件** - 数据库结构变更时，直接修改初始化SQL文件
3. **重新初始化数据库** - 删除现有数据库，重新创建和初始化
4. **无向后兼容要求** - 开发阶段不需要考虑数据迁移和向后兼容
5. **清理迁移文件** - 定期清理不必要的迁移文件，保持项目简洁

### 开发阶段操作流程

当需要修改数据库结构时：

1. 修改SQLAlchemy模型定义
2. 修改数据库初始化SQL文件 (`backend/database/init/`)
3. 删除并重新创建数据库容器
4. 重新初始化数据库

### 生产环境迁移策略

生产环境部署时，将根据最终的模型定义创建完整的迁移脚本。

#### 目录结构

```
backend/
├── alembic/
│   ├── versions/          # 迁移脚本目录（开发阶段保持最小化）
│   ├── env.py            # Alembic环境配置
│   └── script.py.mako    # 迁移脚本模板
├── alembic.ini           # Alembic配置文件
└── models/               # SQLAlchemy模型定义
```
