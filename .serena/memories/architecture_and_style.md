# Project Architecture and Code Style

## Backend Architecture (Layered Pattern)

The backend follows a strict layered architecture with clear separation of concerns:

### Layer Structure
1. **API Layer** (`backend/app/api/v1/`): Route definitions and request handling
2. **Service Layer** (`backend/app/services/`): Business logic and orchestration
3. **Data Layer** (`backend/app/services/*/data/`): Complex queries and business-related data operations
4. **CRUD Layer** (`backend/app/crud/`): Basic database operations
5. **Models Layer** (`backend/app/models/`): SQLAlchemy models

### Key Principles
- Each layer only depends on layers below it
- Data flows down through the layers
- Higher layers don't access lower layers directly
- No circular dependencies between layers

## Directory Structure

```
backend/app/
├── admin/                  # Starlette Admin interface
│   ├── views/             # Admin view controllers
│   └── templates/         # Admin HTML templates
├── api/                   # REST API endpoints
│   ├── v1/               # API version 1
│   └── admin/            # Admin API endpoints
├── core/                 # Core configuration and database
├── models/               # SQLAlchemy models
│   ├── ai/              # AI-related models
│   ├── message/         # Message models
│   └── system/          # System models
├── services/             # Business logic layer
│   ├── admin/           # Admin-specific services
│   ├── ai/              # AI conversation services
│   ├── llm/             # LLM integration
│   └── message/         # Message processing
├── schemas/              # Pydantic schemas
├── crud/                 # Database CRUD operations
└── utils/                # Utility functions
```

## Code Style and Conventions

### Python Standards
- **Type Hints**: Mandatory for all functions and class methods
- **Async/Await**: All database operations and I/O are async
- **Pydantic**: Used for data validation and serialization
- **SQLAlchemy**: Async ORM for database operations
- **Logging**: Structured logging with contextual information

### Naming Conventions
- **Variables/Functions**: snake_case
- **Classes**: PascalCase
- **Constants**: UPPER_SNAKE_CASE
- **Files**: snake_case.py
- **Database Tables**: snake_case

### Error Handling
- Custom exception classes for different error types
- Proper HTTP status codes
- Structured error responses
- Comprehensive logging with context

### Testing Approach
- Unit tests with pytest
- Async test fixtures
- Database transaction rollback in tests
- Mock external dependencies
