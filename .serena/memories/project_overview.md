# SAYS Project Overview

## Project Purpose

SAYS is an AI-powered personalized chat application that creates virtual companions through AI characters. The system focuses on relationship-based conversations with dynamic scoring and state management.

## Tech Stack

- **Backend**: FastAPI + Starlette Admin
- **Database**: PostgreSQL 16 with SQLAlchemy (async)
- **AI/LLM**: Volcengine (Doubao), supports multiple providers
- **Message Processing**: 11-step conversation pipeline with JSON Schema validation
- **Deployment**: Docker + Docker Compose
- **Frontend**: Vue.js admin panel (port 5174)
- **Cache**: Redis for session management

## Project Status

- **Stage**: MVP Development
- **Current Focus**: AI character testing functionality and architecture refactoring
- **Environment**: Development with Docker containers
- **Database**: PostgreSQL running on port 5432
- **Backend**: FastAPI running on port 8000
- **Admin Panel**: <http://localhost:8000/qiao-dash/> (admin/admin123)

## Key Business Logic

### AI Conversation Flow (11 Steps)

1. Merge short-time messages (buffer)
2. Store in ai_contexts table
3. Find corresponding ai_character
4. Find corresponding relationship_score
5. Find relationship based on ai_style
6. Apply relationship prompt to personality template
7. Get context and merge system prompts
8. Request LLM
9. JSON Schema validation
10. Update ai_relationship_score
11. Reply messages

### Scoring System

- **Algorithm**: V1 Independent Bidirectional Offset
- **Range**: 0-1000 for each dimension
- **Purpose**: Dynamic relationship evolution based on conversation
- **Parameters**: left_sensitivity, right_sensitivity (-100 to 100)

### Core Components

- **AI Instances**: Virtual companions with personalities
- **AI Styles**: Multi-dimensional relationship evaluation
- **AI Personalities**: Prompt templates with JSON Schema
- **Context Management**: Conversation history and state
- **Message Buffer**: Short-time message merging
- **Security**: Attack detection and user risk assessment
