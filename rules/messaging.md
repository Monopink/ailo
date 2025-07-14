# Messaging System

## Message Flow

### Core Processing Pipeline

#### Message Reception Flow

1. **LeanCloud Webhook**: Receives user messages via webhook endpoint
2. **Message Validation**: leanmessage.py validates and structures message
3. **Event Bus Publication**: Publishes RECEIVED_MESSAGE event
4. **Message Router**: Routes message to appropriate AI model instance
5. **Message Storage**: Saves received message to database
6. **AI Processing**: Model processes message and generates response

#### Message Sending Flow

1. **AI Response Generation**: Model generates response content
2. **Message Router Processing**: handle_outgoing_message() processes response
3. **Message ID Generation**: Generates unique backend message ID
4. **Event Bus Publication**: Publishes SEND_MESSAGE event
5. **LeanCloud Delivery**: leanmessage.py sends message via LeanCloud API
6. **Message Storage**: Saves sent message to database

### Message Formats

#### System Message Format (Internal)

```json
{
  "id": "system_1752052373681",
  "type": 9,
  "from": "system",
  "to": "u1002",
  "content": {
    "action": 1,
    "target_message_id": "local_1751776984574_97j85pkjk",
    "status": 3,
    "reason": 6
  },
  "timestamp": "2025-07-09T09:12:53.681Z",
  "service": 1
}
```

#### LeanCloud Transport Format

- Native LeanCloud IM service format
- Encrypted message content
- Includes metadata for routing and processing

#### Structured Message Format (Frontend)

```json
{
  "type": 1,
  "from": "bot_entity_id",
  "to": "user_entity_id",
  "content": "message content",
  "timestamp": "2025-01-01T00:00:00Z",
  "service": 1
}
```

## Message ID Management

### Message ID Types

- **message_id**: Backend-generated unique ID for all messages (format: `msg_{timestamp}_{random_string}`)
- **message_id_client**: Frontend-generated ID for user messages (format: `local_{timestamp}_{random_string}`)

### ID Generation Strategy

- **Received Messages**: Only have `message_id_client` from frontend
- **Sent Messages**: Backend generates `message_id` in message_router
- **Database Storage**: Both IDs stored in message_history table for tracking

### ID Generation Location

- **Frontend IDs**: Generated in frontend messaging service
- **Backend IDs**: Generated in `message_router.generate_message_id()`
- **Character Set**: Uses same charset as entity_id for consistency

## Message Types (Enums)

### Message Types

- `1`: CHAT - Regular chat message
- `2`: TYPING - Typing indicator
- `9`: SYSTEM - System notification message

### System Message Actions

- `1`: MESSAGE_STATUS - Update message status

### Message Status

- `3`: FAILED - Message send failed
- `4`: BLOCKED - Message blocked by system
- `5`: DELIVERED - Message successfully delivered

### Failure Reasons

- `1`: NETWORK_ERROR - Network connection failed
- `2`: CONVERSATION_ERROR - Conversation ID issue
- `3`: BLOCKED_BY_USER - Blocked by user
- `4`: SYSTEM_ERROR - Internal system error
- `5`: RATE_LIMITED - Send rate exceeded
- `6`: NOT_CONTACTS - Sender and receiver not contacts
- `7`: CONTENT_TOO_LONG - Message content too long

## LeanCloud Integration

### Unified System Conversation

- All bot messages use single shared conversation ID
- Prioritizes message delivery over ID freshness
- System conversation setup managed by contacts_service

### Webhook Processing

- Only system conversations trigger webhooks
- User-to-user messages handled differently
- Webhook endpoint: `/webhook/leanmessage`

### Message Validation

- Backend validates bot contact relationships
- Checks bot status before processing
- Sends system messages for validation failures

## Encryption

- Message content encrypted before LeanCloud transmission
- Encryption handled by provider layer, not message service layer
- Structured message format maintained after encryption

## Error Handling

### System Message Triggers

- Bot not found → status: 3, reason: 6 (NOT_CONTACTS)
- No permission → status: 3, reason: 6 (NOT_CONTACTS)  
- Bot inactive → status: 3, reason: 3 (BLOCKED_BY_USER)
- Database error → status: 3, reason: 4 (SYSTEM_ERROR)

### Message Failure Recovery

- Failed messages remain in chat interface for retry
- System messages notify frontend of failure reasons
- No automatic retry mechanisms - user-initiated only
