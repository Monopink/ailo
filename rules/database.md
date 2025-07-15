# Database Design

## Core Tables

### users (accounts_service)

- User account information
- Fields: entity_id (string, unique), phone, password_hash, status, role, etc.
- No foreign key constraints - use code logic for relationships

### bots (bot_message_service)

- AI bot information and configuration
- Fields: entity_id (string, unique), model, status, gender, emotion scores, etc.
- Contains emotion system configuration (friend_score, romance_score)
- Includes personality and behavior configuration (JSON fields)
- user_profile_snapshot: JSON field storing user profile snapshots for change detection

### social_profiles

- Unified social profile data for both users and bots
- Fields: entity_id, nickname, bio, avatar_url, birth_date, location, etc.
- Shared by both user and bot entities for consistent profile management

### contacts

- User contact list management
- Fields: user_entity_id, contact_entity_id, contact_type, added_at, etc.
- Manages relationships between users and bots

### conversation_mappings

- LeanCloud conversation ID mapping
- Fields: entity_id, conversation_id, conversation_type, etc.
- Maps internal entity IDs to LeanCloud conversation IDs

### message_history

- Message storage and history
- Fields: message_id, from_entity, to_entity, content, message_type, timestamp, etc.
- Stores all messages for context and history

### emotions

- Emotion state tracking
- Fields: bot_entity_id, user_entity_id, emotion_type, score, updated_at, etc.
- Tracks relationship development and emotional states

### template_mappings & bot_templates

- Contact search and addition functionality
- Supports bot discovery and contact management

## Design Principles

### Entity ID System

- **Global Uniqueness**: All entity_id values are globally unique across the entire system
- All entities use string-based entity_id with configurable prefix (default: 'qqid_')
- No database auto-increment IDs exposed to API
- Consistent ID format across all services
- **Frontend Mapping**: Frontend 'id' field always maps to backend 'entity_id'

### No Foreign Keys

- Avoid database foreign key constraints
- Use application logic for relationship management
- Enables better service decoupling

### Service Data Ownership

- accounts_service: users table
- bot_message_service: bots, message_history, emotions tables
- contacts_service: contacts, social_profiles, conversation_mappings tables

### Data Consistency

- Each service manages its own data integrity
- Cross-service data synchronization through API calls
- No shared database access between services

## Key Constraints

### MVP Development

- No data migration support needed
- No backward compatibility requirements
- Schema changes can be breaking

### String-based IDs

- Frontend uses 'id' field mapping to backend 'entity_id'
- Consistent string type across all entity references
- No numeric ID exposure in APIs

### JSON Configuration Fields

- Bot configuration stored as JSON for flexibility
- Emotion system configuration in JSON format
- Override configurations supported
