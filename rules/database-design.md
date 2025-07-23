# Database Design Principles

## Core Design Philosophy

### MVP Development Approach
- **No Backward Compatibility**: Breaking changes are acceptable during MVP phase
- **No Default Values**: Never hide errors with default values or fallback mechanisms
- **Explicit Error Handling**: All errors must be explicitly handled and reported
- **No Data Migration**: No migration strategies needed during development phase

### Architecture Principles

#### 1. Dependency Inversion Principle
- API layer should not directly depend on database implementations
- Use abstract interfaces (AsyncSession) for database operations
- Enable easy testing and module replacement

#### 2. Single Responsibility Principle
- **API Layer**: Request handling, parameter validation, authentication
- **Service Layer**: Business logic processing
- **Data Layer**: Data access and persistence operations

#### 3. Transaction Consistency
- API layer controls transaction boundaries
- All operations within a single request share the same transaction
- Ensure data consistency across related operations

## Implementation Standards

### API Layer Pattern

```python
# Required imports
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from api.deps import get_db, get_current_user

# Standard API function signature
@router.get("/resource")
async def get_resource(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """API endpoint with dependency injection"""
    result = await service_function(db, current_user.entity_id)
    return {"status": "success", "data": result}
```

### Service Layer Pattern

```python
# Required imports
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any, Optional

# Standard service function signature
async def service_function(
    session: AsyncSession, 
    param1: str, 
    param2: Optional[str] = None
) -> Dict[str, Any]:
    """
    Service function with explicit session parameter
    
    Args:
        session: Database session (injected from API layer)
        param1: Required parameter
        param2: Optional parameter
        
    Returns:
        Result dictionary
        
    Raises:
        ValueError: When validation fails
        Exception: When database operation fails
    """
    try:
        # Database operations using the injected session
        result = await session.execute(query)
        return {"data": result}
    except Exception as e:
        logger.error("operation_failed", error=str(e))
        raise
```

### Independent Task Pattern

```python
# For background tasks not in FastAPI request context
from core.database import SessionLocal

async def background_task():
    """Background task with own session management"""
    async with SessionLocal() as session:
        await process_data(session)
```

## Mandatory Rules

### 1. Type Annotations
- **MUST**: All service functions use `session: AsyncSession` parameter
- **MUST**: Import `AsyncSession` from `sqlalchemy.ext.asyncio`
- **MUST**: Use proper type hints for all parameters and return values

### 2. Session Management
- **MUST**: API layer uses `db: AsyncSession = Depends(get_db)`
- **MUST**: Service layer accepts session as first parameter
- **MUST NOT**: Service layer create own database connections
- **MUST NOT**: Service layer import or use `SessionLocal` directly

### 3. Error Handling
- **MUST**: Explicit error handling in all database operations
- **MUST**: Log errors with structured logging
- **MUST NOT**: Use default values to hide errors
- **MUST NOT**: Implement fallback mechanisms that mask problems

### 4. Transaction Control
- **MUST**: API layer controls transaction boundaries
- **MUST**: Use explicit transactions for multi-step operations
- **MUST**: Ensure proper rollback on errors

## Code Examples

### Correct Implementation

```python
# API Layer
@router.post("/contacts/add")
async def add_contact_endpoint(
    request_data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    contact_id = request_data.get("contact_id")
    if not contact_id:
        raise HTTPException(status_code=400, detail="contact_id is required")
    
    result = await add_contact(db, current_user.entity_id, contact_id)
    return result

# Service Layer
async def add_contact(
    session: AsyncSession, 
    user_entity_id: str, 
    contact_entity_id: str
) -> Dict[str, Any]:
    """Add a new contact relationship"""
    try:
        async with session.begin():
            # Validate user exists
            user = await get_user_by_entity_id(session, user_entity_id)
            if not user:
                raise ValueError(f"User not found: {user_entity_id}")
            
            # Create contact relationship
            contact = Contact(
                user_entity_id=user_entity_id,
                contact_entity_id=contact_entity_id,
                status=1
            )
            session.add(contact)
            
        return {"status": "success", "message": "Contact added"}
    except Exception as e:
        logger.error("add_contact_failed", error=str(e))
        raise
```

### Incorrect Implementation (DO NOT USE)

```python
# WRONG: Service layer managing own connections
async def wrong_service_function(param: str):
    async with SessionLocal() as session:  # DON'T DO THIS
        # Service should not manage connections
        pass

# WRONG: Missing type annotations
async def wrong_function(session, param):  # DON'T DO THIS
    # Missing AsyncSession type annotation
    pass

# WRONG: API layer not using dependency injection
@router.get("/resource")
async def wrong_endpoint():  # DON'T DO THIS
    async with SessionLocal() as db:  # API should use dependency injection
        pass
```

## Testing Guidelines

### Unit Testing Service Layer

```python
import pytest
from unittest.mock import AsyncMock
from sqlalchemy.ext.asyncio import AsyncSession

@pytest.fixture
def mock_session():
    return AsyncMock(spec=AsyncSession)

async def test_service_function(mock_session):
    # Mock database responses
    mock_session.execute.return_value.scalar_one_or_none.return_value = mock_data
    
    # Test service function
    result = await service_function(mock_session, "test_param")
    
    # Verify results
    assert result is not None
    mock_session.execute.assert_called_once()
```

### Integration Testing API Layer

```python
from httpx import AsyncClient
from fastapi.testclient import TestClient

async def test_api_endpoint():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/resource")
        assert response.status_code == 200
```

## Performance Considerations

### Connection Pool Configuration

```python
# Optimal settings for production
engine = create_async_engine(
    database_url,
    pool_pre_ping=True,      # Health check connections
    pool_recycle=300,        # Recycle connections every 5 minutes
    pool_size=20,            # Base connection pool size
    max_overflow=30,         # Additional connections when needed
    echo=False               # Disable SQL logging in production
)
```

### Query Optimization
- Use appropriate database indexes
- Avoid N+1 query problems
- Use batch operations for multiple records
- Implement proper pagination for large datasets

### Transaction Optimization
- Keep transactions as short as possible
- Avoid long-running operations within transactions
- Use appropriate isolation levels
- Release connections promptly

## Migration from Legacy Patterns

### Step-by-Step Migration

1. **Identify Legacy Code**
   - Functions using `SessionLocal()` directly in service layer
   - Missing type annotations
   - API endpoints not using dependency injection

2. **Update Service Layer**
   ```python
   # Before
   async def old_function(param: str):
       async with SessionLocal() as session:
           pass
   
   # After
   async def new_function(session: AsyncSession, param: str):
       # Use injected session
       pass
   ```

3. **Update API Layer**
   ```python
   # Before
   @router.get("/resource")
   async def old_endpoint():
       async with SessionLocal() as db:
           pass
   
   # After
   @router.get("/resource")
   async def new_endpoint(db: AsyncSession = Depends(get_db)):
       pass
   ```

4. **Add Type Imports**
   ```python
   from sqlalchemy.ext.asyncio import AsyncSession
   ```

5. **Update Function Calls**
   - Pass `db` session from API to service layer
   - Remove internal session creation in services

## Validation Checklist

Before submitting code, verify:

- [ ] All service functions have `session: AsyncSession` parameter
- [ ] API endpoints use `db: AsyncSession = Depends(get_db)`
- [ ] No `SessionLocal()` usage in service layer
- [ ] Proper type annotations on all functions
- [ ] Explicit error handling without default values
- [ ] Transaction boundaries controlled by API layer
- [ ] Structured logging for all database operations
- [ ] No backward compatibility or migration code
