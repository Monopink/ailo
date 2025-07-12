/**
 * Message Status Manager
 * 
 * Manages message states independently of transport layer (LeanCloud, etc.)
 * Handles business logic for message delivery status, retries, and system messages
 */

import { MessageStatus, MessageFailureReason } from './types.js'

export class MessageStatusManager {
  constructor() {
    this.pendingMessages = new Map() // localId -> message
    this.statusCallbacks = new Set()
    this.systemMessageCallbacks = new Set()
  }

  /**
   * Register a message as pending
   */
  registerPendingMessage(message) {
    if (!message.localId) {
      throw new Error('Message must have localId')
    }

    message.status = MessageStatus.PENDING
    message.retryCount = message.retryCount || 0

    this.pendingMessages.set(message.localId, message)
    this._notifyStatusChange(message)

    console.log('📝 Message registered as pending:', message.localId)
    return message
  }

  /**
   * Mark message as sent by transport layer
   */
  markTransportSent(localId, transportResponse = {}) {
    const message = this.pendingMessages.get(localId)
    if (!message) {
      console.warn('⚠️ Attempted to mark unknown message as sent:', localId)
      return null
    }

    message.status = MessageStatus.SENT
    message.transportResponse = transportResponse
    message.errorMessage = null
    message.failureReason = null

    // Keep in pending map until system confirms or times out
    this._notifyStatusChange(message)

    console.log('✅ Message marked as transport sent:', localId)
    return message
  }

  /**
   * Mark message as failed by transport layer
   */
  markTransportFailed(localId, error, failureReason = MessageFailureReason.NETWORK_ERROR) {
    const message = this.pendingMessages.get(localId)
    if (!message) {
      console.warn('⚠️ Attempted to mark unknown message as failed:', localId)
      return null
    }

    message.status = MessageStatus.FAILED
    message.providerError = error.message || error.toString() // Store provider error separately
    message.failureReason = failureReason
    message.canRetry = this._canRetry(message, failureReason)

    this._notifyStatusChange(message)

    console.log('❌ Message marked as transport failed:', localId, error.message)
    return message
  }

  /**
   * Mark message as blocked by system
   */
  markSystemBlocked(localId, reason = 'Message blocked by system') {
    const message = this.pendingMessages.get(localId)
    if (!message) {
      console.warn('⚠️ Attempted to mark unknown message as blocked:', localId)
      return null
    }

    message.status = MessageStatus.BLOCKED
    message.errorMessage = reason
    message.failureReason = MessageFailureReason.BLOCKED_BY_USER
    message.canRetry = false

    this._notifyStatusChange(message)

    console.log('🚫 Message marked as system blocked:', localId, reason)
    return message
  }

  /**
   * Mark message as delivered (final success state)
   */
  markDelivered(localId) {
    const message = this.pendingMessages.get(localId)
    if (!message) {
      console.warn('⚠️ Attempted to mark unknown message as delivered:', localId)
      return null
    }

    message.status = MessageStatus.DELIVERED
    message.errorMessage = null
    message.failureReason = null

    // Remove from pending map as it's now complete
    this.pendingMessages.delete(localId)
    this._notifyStatusChange(message)

    console.log('🎉 Message marked as delivered:', localId)
    return message
  }

  /**
   * Retry a failed message
   */
  retryMessage(localId) {
    console.log('🔄 Attempting to retry message:', localId)
    console.log('📊 Current pending messages:', Array.from(this.pendingMessages.keys()))

    const message = this.pendingMessages.get(localId)
    if (!message) {
      console.warn('⚠️ Attempted to retry unknown message:', localId)
      console.log('📊 Available messages:', Array.from(this.pendingMessages.entries()))
      return null
    }

    if (!message.canRetry) {
      console.warn('⚠️ Message cannot be retried:', localId)
      return null
    }

    // Create a new message for retry with updated timestamp
    const retryMessage = {
      ...message,
      status: MessageStatus.PENDING,
      retryCount: (message.retryCount || 0) + 1,
      errorMessage: null,
      failureReason: null,
      timestamp: new Date(), // Update timestamp to move to bottom
      isRetry: true // Mark as retry for UI handling
    }

    // Update the pending message
    this.pendingMessages.set(localId, retryMessage)

    this._notifyStatusChange(retryMessage)

    console.log('🔄 Message retry initiated:', localId, 'attempt:', retryMessage.retryCount)
    return retryMessage
  }

  /**
   * Get message by local ID
   */
  getMessage(localId) {
    return this.pendingMessages.get(localId)
  }

  /**
   * Get all pending messages
   */
  getPendingMessages() {
    return Array.from(this.pendingMessages.values())
  }

  /**
   * Clear completed messages (for cleanup)
   */
  clearCompletedMessages() {
    const completed = []
    for (const [localId, message] of this.pendingMessages.entries()) {
      if (message.status === MessageStatus.DELIVERED ||
        (message.status === MessageStatus.FAILED && !message.canRetry)) {
        completed.push(message)
        this.pendingMessages.delete(localId)
      }
    }
    console.log('🧹 Cleared completed messages:', completed.length)
    return completed
  }

  /**
   * Register status change callback
   */
  onStatusChange(callback) {
    this.statusCallbacks.add(callback)
  }

  /**
   * Unregister status change callback
   */
  offStatusChange(callback) {
    this.statusCallbacks.delete(callback)
  }

  /**
   * Register system message callback
   */
  onSystemMessage(callback) {
    this.systemMessageCallbacks.add(callback)
  }

  /**
   * Unregister system message callback
   */
  offSystemMessage(callback) {
    this.systemMessageCallbacks.delete(callback)
  }

  /**
   * Process incoming system message
   */
  processSystemMessage(systemMessage) {
    console.log('📨 Processing system message:', systemMessage)

    // Handle new structured system message format
    if (systemMessage.content && typeof systemMessage.content === 'object') {
      const { action, target_message_id, status, reason, message, contact_id, contact_name } = systemMessage.content

      if (action === 1 && target_message_id) { // action: 1 = MESSAGE_STATUS
        const targetMessage = this.pendingMessages.get(target_message_id)

        if (targetMessage) {
          // Update message status based on system message
          switch (status) {
            case 3: // FAILED
              targetMessage.status = MessageStatus.FAILED
              targetMessage.systemMessage = message || null // Store system message separately
              targetMessage.failureReason = this._mapReasonToFailureReason(reason)
              targetMessage.canRetry = this._canRetryByReason(reason)
              break

            case 4: // BLOCKED
              targetMessage.status = MessageStatus.BLOCKED
              targetMessage.systemMessage = message || null // Store system message separately
              targetMessage.failureReason = MessageFailureReason.BLOCKED_BY_USER
              targetMessage.canRetry = false
              break

            case 5: // DELIVERED
              targetMessage.status = MessageStatus.DELIVERED
              targetMessage.systemMessage = null
              break
          }

          this._notifyStatusChange(targetMessage)
          console.log('✅ System message processed for:', target_message_id, 'status:', status)
          return
        }
      } else if (action === 2) { // action: 2 = NEW_CONTACT
        // Handle new contact notification
        console.log('📨 New contact system message:', contact_name, contact_id)

        // Trigger contact list refresh
        this._handleNewContactNotification(contact_id, contact_name)

        // Replace content with display message for chat interface
        systemMessage.content = '对方已经添加你为联系人'

        // Continue to notify callbacks for chat display
      }
    }

    // No fallback needed - all system messages should use structured format

    // Notify system message callbacks
    this.systemMessageCallbacks.forEach(callback => {
      try {
        callback(systemMessage)
      } catch (error) {
        console.error('Error in system message callback:', error)
      }
    })
  }

  // Private methods

  /**
   * Handle new contact notification
   */
  _handleNewContactNotification(contactId, contactName) {
    try {
      // Import chat store to trigger contact list refresh
      import('../../stores/chat.js').then(({ useChatStore }) => {
        const chatStore = useChatStore()
        chatStore.fetchContacts()
        console.log('✅ Contact list refreshed after new contact notification')
      })
    } catch (error) {
      console.error('Error handling new contact notification:', error)
    }
  }

  /**
   * Determine if message can be retried
   */
  _canRetry(message, failureReason) {
    const maxRetries = 3

    if ((message.retryCount || 0) >= maxRetries) {
      return false
    }

    // Some failure reasons don't allow retry
    const noRetryReasons = [
      MessageFailureReason.BLOCKED_BY_USER,
      MessageFailureReason.RATE_LIMITED
    ]

    return !noRetryReasons.includes(failureReason)
  }

  /**
   * Extract local_id from system message
   * System messages should include local_id in content or metadata
   */
  _extractLocalIdFromSystemMessage(systemMessage) {
    // Try to extract from content using regex
    const localIdMatch = systemMessage.content?.match(/local_([a-zA-Z0-9_]+)/);
    if (localIdMatch) {
      return localIdMatch[0]; // Return full local_id including 'local_' prefix
    }

    // Try to extract from metadata if available
    if (systemMessage.metadata && systemMessage.metadata.local_id) {
      return systemMessage.metadata.local_id;
    }

    console.warn('Could not extract local_id from system message:', systemMessage);
    return null;
  }

  /**
   * Notify status change callbacks
   */
  _notifyStatusChange(message) {
    this.statusCallbacks.forEach(callback => {
      try {
        callback(message)
      } catch (error) {
        console.error('Error in status change callback:', error)
      }
    })
  }

  /**
   * Map system message reason to MessageFailureReason
   */
  _mapReasonToFailureReason(reason) {
    switch (reason) {
      case 1:
        return MessageFailureReason.NETWORK_ERROR
      case 2:
        return MessageFailureReason.CONVERSATION_ERROR
      case 3:
        return MessageFailureReason.BLOCKED_BY_USER
      case 4:
        return MessageFailureReason.SYSTEM_ERROR
      case 5:
        return MessageFailureReason.RATE_LIMITED
      case 6:
        return MessageFailureReason.NOT_CONTACTS
      case 7:
        return MessageFailureReason.CONTENT_TOO_LONG
      default:
        return MessageFailureReason.SYSTEM_ERROR
    }
  }

  /**
   * Check if message can be retried based on reason
   */
  _canRetryByReason(reason) {
    switch (reason) {
      case 1: // NETWORK_ERROR
        return true
      case 2: // CONVERSATION_ERROR
        return true
      case 3: // BLOCKED_BY_USER
        return false
      case 4: // SYSTEM_ERROR
        return true
      case 5: // RATE_LIMITED
        return true
      case 6: // NOT_CONTACTS
        return false
      case 7: // CONTENT_TOO_LONG
        return false
      default:
        return true
    }
  }
}

// Global instance
export const messageStatusManager = new MessageStatusManager()
