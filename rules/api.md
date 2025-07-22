# API Design Rules

## Service Endpoints

### backend (Port 8000)

- **Base Path**: `/api/v1`
- **Authentication**: JWT Bearer tokens
- **Responsibilities**:
  - User registration, login, SMS verification, basic user info
  - Contact management, bot info, social profiles, conversation mapping
  - System conversation management, message status reporting
  - AI model invocation and response generation
  - Message history storage and retrieval

## API Design Principles

### No Database ID Exposure

- **Entity IDs Only**: All responses use string entity_id, never database auto-increment IDs
- **Global Uniqueness**: All entity_id values are globally unique across the entire system
- **Consistent Format**: Entity IDs follow configurable prefix pattern (default: 'qqid_')
- **Frontend Mapping**: Frontend 'id' field always maps to backend 'entity_id'
- **Security**: No internal database structure exposure

### Error Response Format

```json
{
  "detail": "User-friendly error message"
}
```

### Standard HTTP Status Codes

- `200`: Success
- `400`: Request parameter error  
- `401`: Authentication failed
- `404`: Resource not found
- `500`: Internal server error

## Authentication & Authorization

### JWT Token Management

- **Token Format**: Bearer tokens in Authorization header
- **Token Validation**: Each service validates tokens independently
- **No Shared Sessions**: Stateless authentication across services

### Internal Service Communication

- **Service Key**: INTERNAL_SERVICE_KEY for service-to-service calls
- **No User Context**: Internal calls don't require user authentication

## Request/Response Patterns

### Unified API Client (Frontend)

```javascript
// All API calls use same pattern
const response = await apiClient.get('/auth/me');
const response = await apiClient.post('/auth/login', { phone, password });
const response = await apiClient.get('/contacts');
```

### Error Handling

```javascript
try {
  const response = await apiClient.post('/auth/login', data);
} catch (error) {
  handleApiError(error, 'login'); // Shows user-friendly message
}
```

## Specific API Requirements

### Contact Management

- **ID Mapping**: Frontend 'id' field maps to backend 'entity_id' (globally unique)
- **User Types**: Use numeric codes (type1, type2) for user type differentiation
- **Frontend Terminology**: Avoid 'bot', 'entity', 'ai' in API responses to frontend
- **Lightweight Endpoints**: Separate endpoints for chat list vs full contact info

### System Messages

- **Async Delivery**: System messages sent asynchronously via LeanCloud
- **Status Updates**: Message status changes communicated through system messages
- **Error Reporting**: Conversation errors reported to system endpoint

### Message Validation

- **Contact Relationship**: Validate sender/receiver are contacts
- **Bot Status**: Check bot active status before processing
- **Content Validation**: Message length and content type validation

## Proxy Configuration (Development)

### Vite Proxy Routes

- `/api/v1/*` → backend:8000

### Production Routing

- Nginx reverse proxy handles routing to backend service
- Single backend service handles all API endpoints

## Rate Limiting & Security

### Request Limits

- SMS verification: Rate limited per phone number
- Login attempts: Rate limited per IP/phone
- Message sending: Rate limited per user

### Input Validation

- **Pydantic Models**: All input validation using Pydantic
- **Sanitization**: Input sanitization for security
- **Type Checking**: Strict type validation on all endpoints

### CORS Configuration

- **Strict Origins**: Only allow configured frontend origins
- **Credentials**: Support for authenticated requests
- **Headers**: Allow necessary authentication headers

## Development Practices

### API Documentation

- **OpenAPI/Swagger**: Auto-generated documentation
- **Examples**: Include request/response examples
- **Error Codes**: Document all possible error responses

### Testing

- **Health Checks**: All services provide `/health` endpoint
- **Test Accounts**: Predefined test credentials for development
- **Mock Responses**: LeanCloud and LLM APIs mocked in development
