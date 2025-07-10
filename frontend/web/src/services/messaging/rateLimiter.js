/**
 * Message rate limiter for preventing spam and abuse
 */

import { MessageConstraints } from './types'

class MessageRateLimiter {
  constructor() {
    this.messageHistory = []  // Array of {timestamp}
    this.isBlocked = false
    this.blockEndTime = 0
  }

  /**
   * Check if message can be sent
   * @param {string} content - Message content (for length validation)
   * @param {string} contactId - Contact ID (unused in new logic)
   * @returns {Object} - {canSend: boolean, reason?: string, waitTime?: number}
   */
  canSendMessage(content, contactId) {
    const now = Date.now()

    // Check if currently blocked
    if (this.isBlocked && now < this.blockEndTime) {
      return {
        canSend: false,
        reason: 'rate_limited',
        waitTime: this.blockEndTime - now
      }
    }

    // Clear block if expired
    if (this.isBlocked && now >= this.blockEndTime) {
      this.isBlocked = false
      this.blockEndTime = 0
    }

    // Clean old messages from history (keep only messages in time window)
    this.messageHistory = this.messageHistory.filter(
      msg => now - msg.timestamp < MessageConstraints.RATE_LIMIT.TIME_WINDOW
    )

    // Check if user has sent too many messages in time window
    if (this.messageHistory.length >= MessageConstraints.RATE_LIMIT.MESSAGE_COUNT_LIMIT) {
      // Block user for specified duration
      this.isBlocked = true
      this.blockEndTime = now + MessageConstraints.RATE_LIMIT.BLOCK_DURATION

      return {
        canSend: false,
        reason: 'too_many_messages',
        waitTime: MessageConstraints.RATE_LIMIT.BLOCK_DURATION
      }
    }

    return { canSend: true }
  }

  /**
   * Record a sent message
   * @param {string} content - Message content (unused in new logic)
   * @param {string} contactId - Contact ID (unused in new logic)
   */
  recordMessage(content, contactId) {
    const now = Date.now()

    this.messageHistory.push({
      timestamp: now
    })

    // Keep only recent messages to prevent memory leak
    if (this.messageHistory.length > 50) {
      this.messageHistory = this.messageHistory.slice(-25)
    }
  }

  /**
   * Get user-friendly message for rate limit reason
   * @param {string} reason - Rate limit reason
   * @param {number} waitTime - Wait time in milliseconds (unused)
   * @returns {string} - User-friendly message
   */
  getRateLimitMessage(reason, waitTime) {
    // Simple message without time details
    return '消息发送过快'
  }

  /**
   * Clear all rate limit data (for logout/reset)
   */
  reset() {
    this.messageHistory = []
    this.isBlocked = false
    this.blockEndTime = 0
  }
}

// Create singleton instance
export const messageRateLimiter = new MessageRateLimiter()

// Export class for testing
export { MessageRateLimiter }
