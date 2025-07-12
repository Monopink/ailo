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
  TYPE1: 1,  // User contacts
  TYPE2: 2   // Bots contacts
}

// Message constraints
export const MessageConstraints = {
  MAX_LENGTH: 50,  // Maximum message length in characters
  RATE_LIMIT: {
    MESSAGE_COUNT_LIMIT: 7,      // Max messages in time window
    TIME_WINDOW: 7000,           // 7 seconds time window
    BLOCK_DURATION: 5000         // 5 seconds block duration
  }
}

// Security functions
export const MessageSecurity = {
  /**
   * Sanitize message content to prevent XSS
   * @param {string} content - Raw message content
   * @returns {string} - Sanitized content
   */
  sanitizeContent(content) {
    if (typeof content !== 'string') return ''

    // Remove HTML tags and trim whitespace
    return content
      .replace(/<[^>]*>/g, '')  // Remove HTML tags
      .replace(/javascript:/gi, '')  // Remove javascript: protocol
      .replace(/on\w+\s*=/gi, '')  // Remove event handlers
      .trim()
  }
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

// System message actions
export const SystemMessageAction = {
  MESSAGE_STATUS: 1,  // Update message status and failure reason
  NEW_CONTACT: 2      // New contact added notification
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

// Conversation error types (numeric values for security)
export const ConversationErrorType = {
  CONNECTION_FAILED: 1,
  CONVERSATION_NOT_FOUND: 2,
  PERMISSION_DENIED: 3,
  TIMEOUT: 4,
  UNKNOWN: 5
}

// Multi-device login device types (numeric values for client-facing code)
export const DeviceType = {
  WEB: 1,
  MOBILE: 2,
  PAD: 3,
  DESKTOP: 4
}

// Device type labels for display
export const DeviceTypeLabels = {
  [DeviceType.WEB]: 'Web',
  [DeviceType.MOBILE]: 'Mobile',
  [DeviceType.PAD]: 'Pad',
  [DeviceType.DESKTOP]: 'Desktop'
}

// Multi-device login strategies (numeric values for client-facing code)
export const LoginStrategy = {
  UNLIMITED: 1,     // No restrictions on multi-device login
  SINGLE_DEVICE: 2, // Only one device allowed
  LIMITED_MULTI: 3  // Limited multi-device (different device types)
}

// Login strategy labels for display
export const LoginStrategyLabels = {
  [LoginStrategy.UNLIMITED]: 'unlimited',
  [LoginStrategy.SINGLE_DEVICE]: 'single',
  [LoginStrategy.LIMITED_MULTI]: 'limited'
}

// Login conflict actions (numeric values for client-facing code)
export const ConflictAction = {
  FORCE_LOGOUT: 1,    // Force logout older device
  REJECT_NEW: 2,      // Reject new login attempt
  NOTIFY_ONLY: 3      // Just notify, allow both
}

// Conflict action labels for display
export const ConflictActionLabels = {
  [ConflictAction.FORCE_LOGOUT]: 'force_logout',
  [ConflictAction.REJECT_NEW]: 'reject_new',
  [ConflictAction.NOTIFY_ONLY]: 'notify_only'
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
    transportMessage: createMessage(type, from, to, content, { ...options, id: localId }),

    // Display fields
    text: content,
    sender: from === options.currentUserId ? 'self' : 'other',
    timestamp: new Date(),
    messageType: type,

    // System fields
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
