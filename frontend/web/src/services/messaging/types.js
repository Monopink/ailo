/**
 * Frontend message types and structures
 * Numbers match backend definitions
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

/**
 * Create a standardized message object
 */
export function createMessage(type, from, to, content = '', options = {}) {
  return {
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
