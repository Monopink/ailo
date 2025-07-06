/**
 * Frontend message types and structures
 * Numbers match backend definitions
 *
 * Message Format Documentation:
 * See docs/message-formats.md for complete format specifications
 */

export const MessageType = {
  CHAT: 1,
  TYPING: 2,
  TYPING_END: 3,
  CHAT_NOTYPING: 8,
  SYSTEM: 9
}

export const ContactType = {
  USER: 1,
  BOT: 2
}

// Service types
export const ServiceType = {
  LEANCLOUD: 1
}

// Encryption algorithms (numeric codes for efficiency)
export const EncryptionType = {
  NONE: 0,        // No encryption (for backward compatibility)
  BASE64: 1,      // Base64 encoding (pseudo-encryption)
  AES_256_GCM: 2  // AES-256-GCM (future implementation)
}

// Encryption versions
export const EncryptionVersion = {
  V1: 1  // First version of encryption implementation
}

// Message status for UI state management (independent of transport layer)
export const MessageStatus = {
  PENDING: 1,     // Message is being sent
  SENT: 2,        // Transport layer confirmed delivery
  FAILED: 3,      // Transport layer failed to deliver
  BLOCKED: 4,     // System determined message was blocked
  DELIVERED: 5    // System confirmed successful delivery
}

// Message failure reasons
export const MessageFailureReason = {
  NETWORK_ERROR: 1,
  CONVERSATION_ERROR: 2,
  BLOCKED_BY_USER: 3,
  SYSTEM_ERROR: 4,
  RATE_LIMITED: 5,
  NOT_CONTACTS: 6,           // You and the recipient are not contacts yet
  CONTENT_TOO_LONG: 7
}

/**
 * Generate unique local message ID
 */
export function generateLocalMessageId() {
  return `local_${Date.now()}_${Math.random().toString(36).substring(2, 11)}`
}

/**
 * Create a standardized message object
 */
export function createMessage(type, from, to, content = '', options = {}) {
  return {
    id: options.id || generateLocalMessageId(), // Add id field
    type,
    from,
    to,
    content,
    timestamp: new Date().toISOString(),
    service: 1, // 1 = leancloud service
    ...options
  }
}

/**
 * Create a UI message object with status management
 */
export function createUIMessage(type, from, to, content = '', options = {}) {
  const localId = generateLocalMessageId()

  return {
    // UI-specific fields
    id: localId, // Use localId as id for compatibility with chat store
    localId,
    status: MessageStatus.PENDING,
    retryCount: 0,
    errorMessage: null,
    failureReason: null,

    // Transport message fields
    transportMessage: createMessage(type, from, to, content, options),

    // Display fields
    text: content,
    sender: from === options.currentUserId ? 'user' : 'bot',
    timestamp: new Date(),
    messageType: type,

    // System fields
    isSystemMessage: type === MessageType.SYSTEM,
    canRetry: true,

    ...options
  }
}

/**
 * Create a chat message
 */
export function createChatMessage(from, to, content) {
  return createMessage(MessageType.CHAT, from, to, content)
}

/**
 * Create a typing indicator message
 */
export function createTypingMessage(from, to) {
  return createMessage(MessageType.TYPING, from, to)
}

/**
 * Create a typing end message
 */
export function createTypingEndMessage(from, to) {
  return createMessage(MessageType.TYPING_END, from, to)
}

/**
 * Validate message structure
 */
export function validateMessage(message) {
  if (!message || typeof message !== 'object') {
    return {
      isValid: false,
      errors: ['Message is null or not an object']
    }
  }

  const errors = []
  const requiredFields = ['type', 'from', 'to', 'timestamp', 'service']

  for (const field of requiredFields) {
    if (!message.hasOwnProperty(field)) {
      errors.push(`Missing required field: ${field}`)
    }
  }

  return {
    isValid: errors.length === 0,
    errors
  }
}
