# System Architecture

## Overview

AI chat/dating application with service architecture running in WSL2 Docker containers. Uses LeanCloud IM service for messaging and integrates with LLM APIs for intelligent conversations.

## Service Architecture

### Backend (Port 8000)

- **Responsibility**: Backend service handling all application functionality
- **Key Features**:
  - User registration/login with SMS verification
  - JWT token management and authentication
  - Password reset functionality
  - User contact list management
  - Social profile management
  - Contact search and addition functionality
  - LeanCloud webhook message reception
  - AI model invocation and response generation
  - Emotion system and relationship status management
  - Message history storage
  - Event-driven message routing
  - Bot information CRUD operations
  - LeanCloud system conversation management

### Frontend (Port 5173)

- **Technology**: Vue 3 + Vite + Pinia + Vue Router
- **UI Style**: Modern macOS-like design with large border radius, refined elements
- **Key Pages**: Login/register, chat interface, profile, settings

## Message Flow Architecture

### Message Reception Flow

```text
User Message → LeanCloud IM → Webhook → leanmessage.py
                                            ↓
                                       event_bus (RECEIVED_MESSAGE)
                                            ↓
                                    model_router.handle_received_message()
                                            ↓
                                    [Route to AI Model] + [Save to DB]
                                            ↓
                                      model_ailo.receive_message()
```

### Message Sending Flow

```text
AI Model Response → model_router.handle_outgoing_message()
                                    ↓
                            [Generate message_id] + [Save to DB]
                                    ↓
                            event_bus (SEND_MESSAGE)
                                    ↓
                            leanmessage.handle_send_message()
                                    ↓
                            LeanCloud API → User
```

### Dependency Injection Pattern

- **AI Models**: Use `send_message()` and `send_system_message()` functions
- **Decoupled Design**: Models don't directly import model_router
- **Testable Architecture**: Easy to mock callbacks for unit testing

## Service Communication

- **Event Bus**: Decouples message processing and sending logic within the backend service
- **Database Access**: Single backend service manages all database tables
- **API Gateway**: Frontend uses Vite proxy to route requests to backend service

## Data Access Architecture

### Repository Layer (Complex Business Operations)

- **ContactRepository**: Contact relationship management
- **BotRepository**: Bot data and emotion management
- **ProfileRepository**: User profile operations
- **TemplateRepository**: Bot template management

### CRUD Layer (Simple Data Operations)

- **Message CRUD**: Basic message storage (optimized)
- **User CRUD**: Basic user operations
- **SystemConfig CRUD**: Configuration management

### Usage Guidelines

- **Repository**: Complex queries, business logic, data transformation
- **CRUD**: Simple operations, single table access, basic validation

## Key Design Principles

- **Service Decoupling**: Each service has single responsibility
- **Event-driven**: Message processing uses event bus pattern
- **Repository Pattern**: Complex data access through repository layer
- **Dependency Injection**: AsyncSession passed from API to service layer
- **No Backward Compatibility**: MVP development phase, no legacy support
- **Fail-fast**: No default values or fallback mechanisms to hide errors
- **Functional Programming**: Prefer functions over classes where possible

## Development Environment

- **Container Platform**: WSL2 Docker
- **Database**: MySQL 8.0
- **Logging**: Centralized logging with structured format
- **Development Tools**: ngrok for webhook testing, Dozzle for log viewing
