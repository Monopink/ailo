# Messaging System

## Message Flow

### Core Processing Pipeline
1. **Message Reception**: LeanCloud webhook → bot_message_service
2. **Event Bus**: Standardized message object published to event_bus
3. **Message Router**: Routes to appropriate AI model based on bot configuration
4. **AI Processing**: Model processes message and generates response
5. **Response Routing**: Response sent back through event_bus
6. **Message Storage**: Messages stored in MySQL database
7. **Response Delivery**: LeanCloud API sends response to user

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
