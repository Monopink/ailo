# Message Adapter Interface

This document defines the interface that all message adapters must implement to ensure decoupling from specific messaging services.

## Design Principles

1. **Business Layer Independence**: Business logic should not depend on any third-party messaging service
2. **Adapter Pattern**: Each messaging service is wrapped in an adapter that implements a unified interface
3. **Pure Business Objects**: All data passed between layers should be pure JavaScript objects
4. **Easy Replacement**: Switching messaging services should only require implementing a new adapter

## Architecture Layers

```
┌─────────────────────────────────────────┐
│         Application Layer               │
│         (chat.js, etc.)                 │
│  - Only uses business objects           │
│  - Calls MessageService                 │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│         MessageService                  │
│  - Manages message lifecycle            │
│  - Uses adapter via interface           │
│  - Only handles business objects        │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│         Message Adapter                 │
│  - Implements unified interface         │
│  - Converts business ↔ service format   │
│  - Encapsulates service-specific code   │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│    Third-Party Messaging Service        │
│    (LeanCloud, WebSocket, etc.)         │
└─────────────────────────────────────────┘
```

## Business Message Object

All adapters must work with this standard business message object:

```javascript
{
  // Required fields
  msg_id: string,           // Message ID (e.g., "client_1234567890_abc123")
  from: string,             // Sender qiao_id
  to: string,               // Receiver qiao_id
  conv_id: string,          // Conversation ID
  content: string,          // Message content
  message_type: number,     // Message type (1=TEXT, 2=TYPING_START, etc.)
  supports_typing: boolean, // Whether supports typing indicator
  sent_time: number,        // Sent timestamp (milliseconds)

  // Optional fields (managed by MessageService)
  status: number,           // Message status (1=SENDING, 2=SENT, 3=FAILED, 4=RECEIVED)

  // Optional fields (added by adapter)
  lc_msg_id: string,        // LeanCloud message ID (adapter-specific)
  lc_timestamp: number      // LeanCloud timestamp (adapter-specific)
}
```

## Adapter Interface

All message adapters must implement the following interface:

### Methods

#### `connect(userId: string, signature: Object): Promise<void>`

Connect to the messaging service.

**Parameters:**
- `userId`: User's qiao_id
- `signature`: Authentication signature object (format depends on service)

**Returns:** Promise that resolves when connected

**Example:**
```javascript
await adapter.connect('qiao_user001', {
  signature: 'xxx',
  timestamp: 1234567890,
  nonce: 'abc123'
});
```

---

#### `disconnect(): Promise<void>`

Disconnect from the messaging service.

**Returns:** Promise that resolves when disconnected

**Example:**
```javascript
await adapter.disconnect();
```

---

#### `sendMessage(messageData: Object, imConvId: string): Promise<Object>`

Send a message.

**Parameters:**
- `messageData`: Business message object (see Business Message Object above)
- `imConvId`: Service-specific conversation ID

**Returns:** Promise that resolves with the business message object (may include adapter-specific fields)

**Example:**
```javascript
const messageData = {
  msg_id: 'client_1234567890_abc123',
  from: 'qiao_user001',
  to: 'qiao_bot001',
  conv_id: 'conv_xyz789',
  content: 'Hello',
  message_type: 1,
  supports_typing: true,
  sent_time: 1234567890000
};

const sentMessage = await adapter.sendMessage(messageData, 'lc_conv_id_123');
// Returns: { ...messageData, lc_msg_id: 'xxx', lc_timestamp: 123 }
```

---

#### `onMessage(callback: Function): void`

Register a callback for incoming messages.

**Parameters:**
- `callback`: Function that receives a business message object

**Example:**
```javascript
adapter.onMessage((message) => {
  console.log('Received:', message);
  // message is a business message object
});
```

---

#### `onTyping(callback: Function): void`

Register a callback for typing indicators.

**Parameters:**
- `callback`: Function that receives a typing indicator object

**Example:**
```javascript
adapter.onTyping((typing) => {
  console.log('Typing:', typing);
  // typing: { from_qiao_id: 'qiao_id', conv_id: 'conv_id', isTyping: true, sent_time: 1710001111222 }
});
```

---

#### `onError(callback: Function): void`

Register a callback for errors.

**Parameters:**
- `callback`: Function that receives an error object

**Example:**
```javascript
adapter.onError((error) => {
  console.error('Error:', error);
});
```

---

#### `onConnectionChange(callback: Function): void`

Register a callback for connection state changes.

**Parameters:**
- `callback`: Function that receives a connection state string

**Example:**
```javascript
adapter.onConnectionChange((state) => {
  console.log('Connection state:', state);
});
```

---

#### `isConnected(): boolean`

Check if connected to the messaging service.

**Returns:** `true` if connected, `false` otherwise

**Example:**
```javascript
if (adapter.isConnected()) {
  console.log('Connected');
}
```

## Implementation Example

### LeanCloud Adapter (Current Implementation)

```javascript
class LCAdapter {
  // Internal: LeanCloud-specific message class
  class BusinessMessage extends TypedMessage {
    constructor(data) {
      super();
      this.msg_id = data.msg_id;
      this.from = data.from;
      // ... other fields
    }
  }

  async sendMessage(messageData, imConvId) {
    // Convert business object to LeanCloud format
    const lcMessage = new BusinessMessage(messageData);

    // Send via LeanCloud
    const sent = await conversation.send(lcMessage);

    // Return business object with LeanCloud-specific fields
    return {
      ...messageData,
      lc_msg_id: sent.id,
      lc_timestamp: sent.timestamp
    };
  }

  handleMessage(lcMessage) {
    // Convert LeanCloud message to business object
    const businessData = {
      msg_id: lcMessage.msg_id,
      from: lcMessage.from,
      to: lcMessage.to,
      // ... extract all business fields
      status: MESSAGE_STATUS.RECEIVED
    };

    // Trigger callback with business object
    this.triggerMessageCallbacks(businessData);
  }
}
```

### WebSocket Adapter (Example)

```javascript
class WebSocketAdapter {
  async sendMessage(messageData, roomId) {
    // Convert business object to WebSocket format
    const wsMessage = {
      type: 'message',
      room: roomId,
      data: messageData
    };

    // Send via WebSocket
    this.ws.send(JSON.stringify(wsMessage));

    // Return business object
    return messageData;
  }

  handleMessage(wsMessage) {
    // Parse WebSocket message
    const data = JSON.parse(wsMessage);

    // Extract business object
    const businessData = {
      ...data.data,
      status: MESSAGE_STATUS.RECEIVED
    };

    // Trigger callback with business object
    this.triggerMessageCallbacks(businessData);
  }
}
```

## How to Replace Messaging Service

1. **Implement new adapter** following the interface above
2. **Pass adapter to MessageService**:
   ```javascript
   import WebSocketAdapter from './websocket-adapter';
   const wsAdapter = new WebSocketAdapter();
   const messageService = new MessageService(wsAdapter);
   ```
3. **No changes needed** in chat.js or other application code

## Key Points

- ✅ Business layer only uses pure JavaScript objects
- ✅ Adapter encapsulates all service-specific code
- ✅ Service-specific classes (like BusinessMessage) are internal to adapter
- ✅ Replacing service only requires implementing new adapter
- ✅ Application code remains unchanged when switching services
