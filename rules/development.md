# Development Rules

## Core Programming Principles

### Project-Specific Principles

- **Functional Programming Priority**: Use functions over classes where possible
- **Fail-fast Philosophy**: No default values or fallback mechanisms to hide errors
- **Service Decoupling**: Single responsibility with clear boundaries
- **Event-driven Architecture**: Message processing through event bus pattern
- **No Backward Compatibility**: MVP development phase, breaking changes acceptable

### Functional Programming Priority

- **Avoid Classes**: Use functions over classes where possible
- **Pure Functions**: Prefer pure functions for business logic
- **Immutability**: Avoid mutable state where possible
- **Composition**: Build complex functionality through function composition

### Error Handling Philosophy

- **Fail Fast**: No default values or fallback mechanisms
- **Explicit Errors**: Expose errors clearly, don't hide problems
- **No Backward Compatibility**: MVP phase, breaking changes acceptable
- **Early Returns**: Use guard clauses and early returns for error conditions

### Code Organization

- **Single Responsibility**: Each module/function has one clear purpose
- **Decoupling**: Modules communicate through well-defined interfaces
- **Event-driven**: Use event bus pattern for loose coupling
- **Dependency Inversion**: High-level modules should not depend on low-level modules
- **Layered Architecture**: Clear separation between API, Service, and Data layers

## Language-Specific Rules

### Python/FastAPI

- **Type Hints**: All function signatures must have type hints
- **Async/Await**: Use async def for I/O operations, def for pure functions
- **Pydantic Models**: Input validation with Pydantic, not raw dictionaries
- **Descriptive Variables**: Use helper verbs (is_active, has_permission)
- **File Naming**: Lowercase with underscores (services/websocket.py)

### Database Access Patterns

- **API Layer**: Use FastAPI dependency injection with `db: AsyncSession = Depends(get_db)`
- **Service Layer**: Accept `session: AsyncSession` parameter, never create own connections
- **Independent Tasks**: Use `async with SessionLocal() as session:` for background tasks
- **Type Safety**: Always use `AsyncSession` type annotations in service functions
- **Transaction Control**: API layer controls transaction boundaries
- **No Direct SessionLocal**: Service layer must not import or use SessionLocal directly

### JavaScript/Vue.js

- **Composition API**: Use Vue 3 Composition API
- **ES6+ Syntax**: Modern JavaScript features
- **English Comments**: All code comments in English
- **Reactive State**: Proper reactive state management with Pinia
- **Component Structure**: Single File Components with clear separation

### Project-Specific Development Rules

- **English Comments**: Use English comments in code, Chinese for user responses
- **Global Entity IDs**: All entity_id values are globally unique across the entire system
- **String-based Entity IDs**: No database ID exposure, only string entity_id
- **Frontend ID Mapping**: Frontend 'id' field always maps to backend 'entity_id'
- **Frontend Terminology**: Avoid 'bot', 'entity', 'ai' in frontend code and network requests
- **User Type Representation**: Use 'type1', 'type2' for different user types in frontend
- **Structured Logging**: JSON format for all logs
- **No **pycache****: Prevent Python cache generation
- **Package Manager Only**: Always use package managers for dependencies, never edit package files manually
- **Mock APIs**: LeanCloud and LLM APIs use mock responses in development

## Development Environment

### Docker Configuration

- **WSL2 Platform**: All services run in WSL2 Docker containers
- **Service Isolation**: Each service in separate container
- **Volume Mapping**: Development code mounted for hot reload
- **Network**: Services communicate through Docker network

### Database Management

- **No Migrations**: MVP phase, schema changes can be breaking
- **No Foreign Keys**: Use application logic for relationships
- **String IDs**: Entity IDs as strings, no auto-increment exposure
- **Service Ownership**: Each service owns specific tables

### Logging

- **Structured Logging**: JSON format for all logs
- **Centralized**: All logs collected in single location
- **English Messages**: Log messages in English
- **Context Binding**: Include relevant context in log entries

## Testing Strategy

### Development Testing

- **Mock APIs**: LeanCloud and LLM APIs mocked in development
- **Test Data**: Predefined test accounts and data
- **Health Checks**: All services provide health endpoints
- **Manual Testing**: Focus on manual testing over automated tests

### Error Simulation

- **Failure Scenarios**: Test error conditions explicitly
- **Network Issues**: Simulate network failures
- **Invalid Data**: Test with malformed inputs
- **Service Unavailability**: Test service failure scenarios

## Package Management

### Dependency Management

- **Use Package Managers**: Always use npm/pip/etc, never edit package files manually
- **Version Pinning**: Pin versions for stability
- **Minimal Dependencies**: Only include necessary packages
- **Security Updates**: Regular dependency updates

### Python Specific

- **No **pycache****: Prevent Python cache generation
- **Virtual Environments**: Isolated Python environments
- **Requirements Files**: Separate requirements for each service

## Code Quality

### Code Style

- **Consistent Formatting**: Use automated formatters
- **Meaningful Names**: Descriptive variable and function names
- **Short Functions**: Keep functions focused and small
- **Clear Comments**: Explain why, not what

### Review Process

- **Self Review**: Review own code before submission
- **Error Checking**: Verify error handling paths
- **Documentation**: Update rules documentation with changes
- **Testing**: Test changes thoroughly before deployment

## Configuration Management

### Environment Variables

- **Sensitive Data**: All secrets in environment variables
- **Service Configuration**: Each service has own config
- **Default Values**: Avoid defaults that hide configuration issues
- **Validation**: Validate configuration on startup

### File Organization

- **Config Files**: Service-specific configuration files
- **No Shared Config**: Each service manages own configuration
- **Version Control**: Configuration templates in version control
- **Local Overrides**: Local development overrides supported

## Deployment Practices

### Container Strategy

- **Single Responsibility**: One service per container
- **Health Checks**: Container health check endpoints
- **Graceful Shutdown**: Proper shutdown signal handling
- **Resource Limits**: Appropriate resource constraints

### Development Workflow

- **Hot Reload**: Code changes reflected immediately
- **Log Monitoring**: Real-time log viewing with Dozzle
- **Service Restart**: Individual service restart capability
- **Database Reset**: Easy database reset for development
