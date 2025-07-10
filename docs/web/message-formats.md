# Message Format Specification

## Overview

This document defines three message formats and their relationships within the system:

1. **LeanCloud Transport Format** - Native format for LeanCloud IM service
2. **System Message Format** - Our unified message format definition
3. **Encrypted Message Format** - Extended format with encryption metadata

## Architecture Design: Unified System Conversation

### Design Principles

All user-to-bot conversations use a **single unified system conversation**, differentiating between bots through the `entity_id` in message content. This design:

- Reduces LeanCloud resource consumption
- Simplifies conversation management
- Eliminates the need for conversation mapping tables

### Conversation Management

- **User-to-User**: One dedicated conversation per user pair (unchanged)
- **User-to-Bot**: All bots share a single unified system conversation
- **Conversation ID Retrieval**: Frontend fetches via API `/api/v1/system/conversation-id`
- **Caching Strategy**: Frontend memory cache with automatic cleanup and retry on errors

## 1. LeanCloud Transport Format

The native message format used by LeanCloud IM service, which cannot be modified:

```javascript
// LeanCloud send message format
{
  conversationId: "6864d79a9a6e605b27a4ebba",
  message: "JSON string content",  // Our system message format goes here
  fromClientId: "u1002",
  toClientIds: ["b9002"]
}

// LeanCloud webhook receive format
{
  data: {
    _lctext: "JSON string content",  // Our system message format
    _lctype: -1
  },
  from: "u1002",
  conv: { objectId: "6864d79a9a6e605b27a4ebba" },
  // ... other LeanCloud fields
}
```

## 2. System Message Format (Base Version)

Our unified message format for frontend-backend communication:

```javascript
{
  id: "local_1751776984574_97j85pkjk",  // Message ID (local_id for frontend messages)
  type: 1,                    // Message type: 1=chat, 2=typing, 3=typing_end, 9=system
  from: "u1002",             // Sender entity ID
  to: "b9002",               // Recipient entity ID
  content: "Hello World",    // Message content
  timestamp: "2025-07-05T01:03:26.474Z",  // ISO timestamp
  service: 1                 // Service type: 1=LeanCloud
}
```

### Message Type Definitions

- **1** - Chat message
- **2** - Typing indicator
- **3** - Typing end indicator
- **9** - System message

### Service Type Definitions

- **1** - LeanCloud IM service

## 2.1. System Message Format for Status Management

System messages (type=9) are used to notify the frontend about message status changes and business-level failures:

```javascript
{
  id: "system_" + Date.now(),
  type: 9,                    // System message
  from: "b1002",             // Source bot entity ID (for chat window identification)
  to: "u1002",               // Target user
  content: {
    action: 1,                // Action type (numeric)
    target_message_id: "local_1751776984574_97j85pkjk", // Target message ID
    status: 3,                // New status (numeric)
    reason: 6                 // Failure reason (numeric)
    message: "你不是对方的联系人"  // Optional: overrides frontend default message, optional: Default values will be displayed if the front-end is not provided
  },
  timestamp: "2025-07-05T01:03:26.474Z",
  service: 1
}
```

### System Message Actions (Numeric)

- **1** - MESSAGE_STATUS: Update message status and failure reason

### System Message Status Values (Numeric)

- **3** - FAILED: Message failed to send (business logic failure)
- **4** - BLOCKED: Message was blocked by system policy
- **5** - DELIVERED: Message was successfully delivered

### System Message Reason Codes (Numeric)

- **1** - NETWORK_ERROR: Network connection failed
- **2** - CONVERSATION_ERROR: Conversation ID issues
- **3** - BLOCKED_BY_USER: Recipient has blocked the sender
- **4** - SYSTEM_ERROR: Internal system error
- **5** - RATE_LIMITED: Too many messages sent in short time
- **6** - NOT_CONTACTS: Sender not recipient's contact
- **5** - RATE_LIMITED: Message sending rate limit exceeded
- **7** - CONTENT_TOO_LONG: Message content exceeds maximum length limit

## 2.2. System Message Format for Display Only

System messages without action field are displayed in the chat interface:

```javascript
{
  id: "system_" + Date.now(),
  type: 9,                    // System message
  from: "b1002",             // Source bot entity ID (for chat window identification)
  to: "u1002",               // Target user
  content: {
    message: "系统消息内容"      // Message text to display in chat
  },
  timestamp: "2025-07-05T01:03:26.474Z",
  service: 1
}
```

### System Message Display Rules

- **With action field (action: 1)**: Processed for status updates, optionally displayed if message field is present
- **Without action field**: Always displayed in chat interface as system message

## 2.3. Message Security and Rate Limiting

### Content Security

All message content is automatically sanitized to prevent XSS attacks:

- HTML tags are removed
- JavaScript protocols are filtered
- Event handlers are stripped

### Rate Limiting Rules

To prevent spam and abuse, the following rate limits are enforced:

- **Message Length**: Maximum 50 characters per message
- **Same Message**: 10 second interval between identical messages
- **Different Messages**: 1 second interval between any messages
- **Spam Detection**: Maximum 3 identical messages in 20 seconds
- **Temporary Block**: 30 seconds block when spam is detected

### Rate Limit Error Messages

- **RATE_LIMITED (5)**: Various rate limiting scenarios with user-friendly Chinese messages

## 3. Encrypted Message Format (Extended Version)

Extended format containing encryption metadata:

```javascript
{
  id: "local_1751776984574_97j85pkjk",  // Message ID
  type: 1,                    // Message type
  from: "u1002",             // Sender
  to: "b9002",               // Recipient
  content: "SGVsbG8gV29ybGQ=", // Encrypted content (Base64)
  timestamp: "2025-07-05T01:03:26.474Z",
  service: 1,                // LeanCloud service
  encryption: 1,             // Encryption algorithm: 1=Base64, 2=AES-256-GCM
  enc_version: 1             // Encryption version
}
```

### Encryption Algorithm Definitions

- **1** - Base64 encoding (pseudo-encryption)
- **2** - AES-256-GCM (true encryption, future implementation)

### Encryption Version Definitions

- **1** - First encryption implementation

## 4. Message Flow Relationships

### Send Flow

> Frontend creates message → Encryption processing → Wrap in LeanCloud format → Send
> Original format → Encrypted format → LeanCloud transport format

### Receive Flow

> LeanCloud receives → Parse system format → Decryption processing → Business processing
> LeanCloud format → Encrypted format → Original format

### Code Mapping

#### Frontend

- **types.js** - Defines message types and formats
- **messageService.js** - Handles message encryption and format conversion
- **leancloudProvider.js** - Handles LeanCloud format conversion

#### Backend

- **enums.py** - Defines message type enums
- **leanmessage.py** - Handles LeanCloud and system format conversion
- **encryption.py** - Handles message encryption/decryption

## 5. Unencrypted Message Compatibility

### Unencrypted Messages

For messages that don't require encryption, the format remains the same but without encryption fields:

```javascript
{
  id: "local_1751776984574_97j85pkjk",  // Message ID (required)
  type: 1,
  from: "u1002",
  to: "b9002",
  content: "Hello World",    // Plain text content
  timestamp: "2025-07-05T01:03:26.474Z",
  service: 1
  // No encryption or enc_version fields
}
```

### Detection Rules

- If message contains `encryption` field → encrypted message
- If message lacks `encryption` field → unencrypted message (plain text)

## 6. Implementation Notes

1. **LeanCloud format is immutable** - Can only place our JSON string in the `_lctext` field
2. **Numeric encoding preferred** - Use numbers instead of strings for encryption algorithms, versions, etc.
3. **Message ID required** - All messages must include the `id` field for proper tracking and status management
4. **Unencrypted message support** - System supports both encrypted and plain text messages
5. **Error handling** - Fallback strategies for encryption/decryption failures
6. **Performance considerations** - Base64 encoding overhead, future AES encryption overhead

## 7. Test Cases

### Basic Unencrypted Message

```javascript
{
  id: "local_1751776984574_97j85pkjk",
  type: 1,
  from: "u1001",
  to: "u1002",
  content: "test",
  timestamp: "2025-07-05T10:00:00.000Z",
  service: 1
}
```

### Encrypted Message

```javascript
{
  id: "local_1751776984574_97j85pkjk",
  type: 1,
  from: "u1001",
  to: "u1002",
  content: "dGVzdA==",
  timestamp: "2025-07-05T10:00:00.000Z",
  service: 1,
  encryption: 1,
  enc_version: 1
}
```

### System Message

```javascript
{
  id: "system_1751776984574",
  type: 9,
  from: "b1002",
  to: "u1002",
  content: {
    action: 1,
    target_message_id: "local_1751776984574_97j85pkjk",
    status: 3,
    reason: 6
  },
  timestamp: "2025-07-05T10:00:00.000Z",
  service: 1
}
```

### LeanCloud Wrapper

```javascript
{
  data: {
    _lctext: '{"id":"local_1751776984574_97j85pkjk","type":1,"from":"u1001","to":"u1002","content":"dGVzdA==","timestamp":"2025-07-05T10:00:00.000Z","service":1,"encryption":1,"enc_version":1}',
    _lctype: -1
  }
}
```
