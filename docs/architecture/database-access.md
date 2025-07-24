# 数据库访问架构

## 概述

本项目采用统一的数据库访问模式，基于依赖注入和分层架构设计，确保代码的可测试性、可维护性和性能。

## 架构设计原则

### 1. 依赖倒置原则 (Dependency Inversion Principle)

- API层不直接依赖数据库实现
- 通过抽象接口（AsyncSession）进行数据库操作
- 便于单元测试和模块替换

### 2. 单一职责原则 (Single Responsibility Principle)

- **API层**：负责请求处理、参数验证、权限检查
- **服务层**：负责业务逻辑处理
- **仓库层**：负责复杂数据访问和业务相关查询
- **CRUD层**：负责基础数据操作

### 3. 事务一致性

- API层控制事务边界
- 一个请求内的所有操作在同一事务中
- 确保数据一致性

## 实现模式

### API层 (FastAPI 依赖注入)

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from api.deps import get_db, get_current_user

@router.get("/contacts")
async def get_contacts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get user contacts"""
    contact_list = await get_user_contacts(db, current_user.entity_id)
    return {"status": "success", "data": contact_list}
```

### 仓库层 (Repository Pattern)

```python
from repositories.contact_repository import ContactRepository
from repositories.bot_repository import BotRepository

async def get_user_contacts(session: AsyncSession, user_entity_id: str) -> List[Dict[str, Any]]:
    """
    Get all contacts for a user using repository layer

    Args:
        session: Database session
        user_entity_id: User's entity ID

    Returns:
        List of contact dictionaries
    """
    contact_repository = ContactRepository()
    contacts = await contact_repository.get_user_contacts(session, user_entity_id)
    # ... 业务逻辑处理
    return contacts
```

### CRUD层 (简单数据操作)

```python
from crud.message import message_crud

async def save_message_simple(session: AsyncSession, message_data: Dict[str, Any]):
    """
    Simple message saving using CRUD layer

    Args:
        session: Database session
        message_data: Message data dictionary
    """
    return await message_crud.save_message(session, message_data)
```

### 数据库连接管理

```python
# core/database.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# 创建引擎和会话工厂
engine = create_async_engine(settings.database_url, echo=echo_sql)
SessionLocal = async_sessionmaker(
    autocommit=False, 
    autoflush=False, 
    bind=engine, 
    class_=AsyncSession
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖注入函数"""
    async with SessionLocal() as session:
        yield session
```

## 数据访问层选择指南

### 何时使用仓库层 (Repository)

- **复杂业务查询**: 涉及多表关联、复杂条件的查询
- **业务相关操作**: 包含特定业务逻辑的数据操作
- **数据转换**: 需要将数据库模型转换为业务对象
- **示例**: Bot数据管理、Contact关系查询、Profile数据处理

### 何时使用CRUD层

- **简单数据操作**: 基础的增删改查操作
- **单表操作**: 不涉及复杂业务逻辑的操作
- **通用功能**: 可复用的基础数据操作
- **示例**: Message保存、User基础操作、System配置

### 当前实现状态

- ✅ **ContactRepository**: 联系人关系管理
- ✅ **BotRepository**: Bot数据和情感管理
- ✅ **ProfileRepository**: 用户资料管理
- ✅ **TemplateRepository**: Bot模板管理
- ✅ **Message CRUD**: 消息基础操作（已优化）
- ✅ **User CRUD**: 用户基础操作
- ✅ **SystemConfig CRUD**: 系统配置操作

## 使用场景

### 1. API 路由中的标准用法

```python
@router.post("/contacts/add")
async def add_contact_endpoint(
    request_data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    contact_id = request_data.get("contact_id")
    result = await add_contact(db, current_user.entity_id, contact_id)
    return result
```

### 2. 服务层函数设计

```python
async def add_contact(
    session: AsyncSession, 
    user_entity_id: str, 
    contact_entity_id: str
) -> Dict[str, Any]:
    """
    Add a new contact
    
    Args:
        session: Database session (injected from API layer)
        user_entity_id: User's entity ID
        contact_entity_id: Contact's entity ID
        
    Returns:
        Result dictionary with status and message
    """
    # 使用事务确保数据一致性
    async with session.begin():
        # 业务逻辑处理
        pass
```

### 3. 独立任务和后台服务

```python
# 对于不在 FastAPI 请求上下文中的独立任务
async def background_task():
    """后台任务示例"""
    async with SessionLocal() as session:
        # 执行后台任务逻辑
        await process_data(session)
```

## 最佳实践

### 1. 类型注解

- 所有服务层函数必须使用 `AsyncSession` 类型注解
- 确保类型安全和IDE支持

### 2. 错误处理

```python
async def service_function(session: AsyncSession, param: str):
    try:
        # 数据库操作
        result = await session.execute(query)
        return result
    except Exception as e:
        logger.error("operation_failed", error=str(e))
        raise
```

### 3. 事务管理

```python
# 显式事务控制
async with session.begin():
    # 多个相关操作
    await operation1(session)
    await operation2(session)
    # 自动提交或回滚
```

### 4. 测试支持

```python
# 单元测试中可以轻松 mock AsyncSession
@pytest.fixture
async def mock_session():
    return AsyncMock(spec=AsyncSession)

async def test_service_function(mock_session):
    result = await service_function(mock_session, "test_param")
    assert result is not None
```

## 迁移指南

### 从旧模式迁移

**旧模式 (不推荐)**:

```python
async def old_service_function(param: str):
    async with SessionLocal() as session:
        # 服务层自己管理数据库连接
        pass
```

**新模式 (推荐)**:

```python
async def new_service_function(session: AsyncSession, param: str):
    # 接收外部传入的 session
    pass
```

### 迁移步骤

1. **修改服务层函数签名**
   - 添加 `session: AsyncSession` 参数
   - 移除内部的 `SessionLocal()` 使用

2. **更新API层调用**
   - 添加 `db: AsyncSession = Depends(get_db)` 参数
   - 传递 `db` 给服务层函数

3. **添加类型导入**

   ```python
   from sqlalchemy.ext.asyncio import AsyncSession
   ```

## 性能优化

### 1. 连接池配置

```python
engine = create_async_engine(
    database_url,
    pool_pre_ping=True,      # 连接健康检查
    pool_recycle=300,        # 连接回收时间
    pool_size=20,            # 连接池大小
    max_overflow=30          # 最大溢出连接
)
```

### 2. 查询优化

- 使用适当的索引
- 避免 N+1 查询问题
- 使用批量操作

### 3. 事务优化

- 保持事务尽可能短
- 避免长时间持有连接
- 合理使用事务隔离级别

## 故障排除

### 常见问题

1. **连接泄漏**
   - 确保使用 `async with` 语句
   - 检查异常处理中的资源释放

2. **事务死锁**
   - 保持事务操作顺序一致
   - 减少事务持有时间

3. **类型错误**
   - 确保正确导入 `AsyncSession`
   - 检查函数签名类型注解

### 调试技巧

```python
# 启用 SQL 日志
engine = create_async_engine(database_url, echo=True)

# 添加详细日志
logger.debug("database_operation", query=str(query), params=params)
```
