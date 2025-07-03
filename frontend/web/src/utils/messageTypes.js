// Message types and validation - matches backend enums.py

export const MessageTypeCategory = {
  CONTENT: 'content',  // Content messages that need to be saved
  STATUS: 'status',    // Status messages that don't need to be saved
  SYSTEM: 'system'     // System messages
}

export const MessageType = {
  // Chat messages
  CHAT: { code: 1, name: 'chat', category: MessageTypeCategory.CONTENT },
  CHAT_NOTYPING: { code: 8, name: 'chat_notyping', category: MessageTypeCategory.CONTENT },
  
  // Status messages
  TYPING: { code: 2, name: 'typing', category: MessageTypeCategory.STATUS },
  TYPING_END: { code: 3, name: 'typing_end', category: MessageTypeCategory.STATUS },
  
  // System messages
  SYSTEM: { code: 9, name: 'system', category: MessageTypeCategory.SYSTEM }
}

// Helper functions
export function getMessageTypeByCode(code) {
  return Object.values(MessageType).find(type => type.code === code) || null
}

export function getMessageTypeByName(name) {
  return Object.values(MessageType).find(type => type.name === name.toLowerCase()) || null
}

export function isContentMessage(messageType) {
  const type = typeof messageType === 'number' 
    ? getMessageTypeByCode(messageType) 
    : getMessageTypeByName(messageType)
  return type && type.category === MessageTypeCategory.CONTENT
}

export function isStatusMessage(messageType) {
  const type = typeof messageType === 'number' 
    ? getMessageTypeByCode(messageType) 
    : getMessageTypeByName(messageType)
  return type && type.category === MessageTypeCategory.STATUS
}

export function isSystemMessage(messageType) {
  const type = typeof messageType === 'number' 
    ? getMessageTypeByCode(messageType) 
    : getMessageTypeByName(messageType)
  return type && type.category === MessageTypeCategory.SYSTEM
}

// Message validation
export function validateMessage(message) {
  const errors = []
  
  // Required fields
  const requiredFields = ['from_entity', 'to_entity', 'message_type', 'message_service']
  for (const field of requiredFields) {
    if (!message[field]) {
      errors.push(`Missing required field: ${field}`)
    }
  }
  
  // Validate message type
  if (message.message_type && !getMessageTypeByCode(message.message_type)) {
    errors.push(`Invalid message_type: ${message.message_type}`)
  }
  
  // Content messages should have content
  if (message.message_type && isContentMessage(message.message_type) && !message.content) {
    errors.push('Content messages must have content field')
  }
  
  return {
    isValid: errors.length === 0,
    errors
  }
}

// Create structured message
export function createMessage(fromEntity, toEntity, content, messageType = MessageType.CHAT.code) {
  return {
    from_entity: fromEntity,
    to_entity: toEntity,
    content: content,
    message_type: messageType,
    message_service: 'leancloud',
    message_time: new Date().toISOString()
  }
}

// Create typing indicator message
export function createTypingMessage(fromEntity, toEntity) {
  return {
    from_entity: fromEntity,
    to_entity: toEntity,
    message_type: MessageType.TYPING.code,
    message_service: 'leancloud',
    message_time: new Date().toISOString()
  }
}

// Create typing end message
export function createTypingEndMessage(fromEntity, toEntity) {
  return {
    from_entity: fromEntity,
    to_entity: toEntity,
    message_type: MessageType.TYPING_END.code,
    message_service: 'leancloud',
    message_time: new Date().toISOString()
  }
}
