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
  type: 1,                    // Message type: 1=chat, 2=typing, 3=system
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
- **3** - System message

### Service Type Definitions

- **1** - LeanCloud IM service

## 3. Encrypted Message Format (Extended Version)

Extended format containing encryption metadata:

```javascript
{
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

## 5. Backward Compatibility

### Unencrypted Messages

```javascript
{
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
- If message lacks `encryption` field → unencrypted message (backward compatible)

## 6. Implementation Notes

1. **LeanCloud format is immutable** - Can only place our JSON string in the `_lctext` field
2. **Numeric encoding preferred** - Use numbers instead of strings for encryption algorithms, versions, etc.
3. **Backward compatibility** - Must support legacy unencrypted message formats
4. **Error handling** - Fallback strategies for encryption/decryption failures
5. **Performance considerations** - Base64 encoding overhead, future AES encryption overhead

## 7. Test Cases

### Basic Message

```javascript
{type: 1, from: "u1001", to: "u1002", content: "test", timestamp: "2025-07-05T10:00:00.000Z", service: 1}
```

### Encrypted Message

```javascript
{type: 1, from: "u1001", to: "u1002", content: "dGVzdA==", timestamp: "2025-07-05T10:00:00.000Z", service: 1, encryption: 1, enc_version: 1}
```

### LeanCloud Wrapper

```javascript
{
  data: {
    _lctext: '{"type":1,"from":"u1001","to":"u1002","content":"dGVzdA==","timestamp":"2025-07-05T10:00:00.000Z","service":1,"encryption":1,"enc_version":1}',
    _lctype: -1
  }
}
```
