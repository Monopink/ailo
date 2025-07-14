/**
 * Message service abstraction layer
 * Provides unified interface for different message providers
 */

import { LeanCloudProvider } from './providers/leancloudProvider'
import { ContactType, createUIMessage, MessageType, MessageFailureReason, MessageSecurity, MessageStatus } from './types'
import { messageStatusManager } from './messageStatusManager'
import { messageRateLimiter } from './rateLimiter'

class MessageService {
  constructor() {
    this.provider = null
    this.currentUserId = null
    this.isInitialized = false
  }

  /**
   * Initialize message service with a provider
   */
  async initialize(userId, providerType = 'leancloud') {
    try {
      // Create provider instance
      switch (providerType) {
        case 'leancloud':
          this.provider = new LeanCloudProvider()
          break
        default:
          throw new Error(`Unknown provider type: ${providerType}`)
      }

      // Initialize provider
      await this.provider.initialize(userId)
      this.currentUserId = userId
      this.isInitialized = true

      // Set up message callbacks
      this.provider.onMessage(this._handleMessage.bind(this))
      this.provider.onTyping(this._handleTyping.bind(this))

      console.log(`✅ Message service initialized with ${providerType} provider`)
    } catch (error) {
      console.error('❌ Failed to initialize message service:', error)
      throw error
    }
  }

  /**
   * Cleanup message service
   */
  async cleanup() {
    try {
      if (this.provider) {
        await this.provider.cleanup()
        this.provider = null
      }

      // Reset rate limiter
      messageRateLimiter.reset()

      this.currentUserId = null
      this.isInitialized = false
      console.log('✅ Message service cleaned up')
    } catch (error) {
      console.error('❌ Failed to cleanup message service:', error)
    }
  }

  /**
   * Send a chat message with status management
   * Returns UI message object for immediate display
   * Message will be shown immediately and status updated based on transport result
   */
  async sendChatMessage(contact, content) {
    // Sanitize content for security (defensive programming - should already be done in UI)
    const sanitizedContent = MessageSecurity.sanitizeContent(content)

    // Create UI message for immediate display regardless of initialization status
    const uiMessage = createUIMessage(
      MessageType.CHAT,
      this.currentUserId || 'unknown',
      contact.id,
      sanitizedContent,
      { currentUserId: this.currentUserId || 'unknown' }
    )

    // Register message as pending
    messageStatusManager.registerPendingMessage(uiMessage)

    // Check if service is initialized
    if (!this.isInitialized || !this.provider) {
      console.error('❌ Message service not initialized')

      // Mark message as failed immediately
      messageStatusManager.markTransportFailed(
        uiMessage.localId,
        new Error('Message service not initialized'),
        MessageFailureReason.SYSTEM_ERROR
      )

      // Return UI message so it shows in chat with failed status
      return uiMessage
    }

    // Attempt to send via transport layer in background
    // Don't await - let it complete asynchronously while UI shows the message
    this._sendViaProvider(uiMessage, contact).catch(error => {
      console.error('Background send failed:', error)
      // Error handling is done in _sendViaProvider
    })

    // Return UI message for immediate display
    return uiMessage
  }

  /**
   * Send message via provider (background operation)
   */
  async _sendViaProvider(uiMessage, contact) {
    try {
      const options = this._buildMessageOptions(contact)
      // Pass the complete transport message to preserve the ID
      const transportResult = await this.provider.sendChatMessage(
        contact.id,
        uiMessage.transportMessage.content,
        { ...options, messageId: uiMessage.transportMessage.id }
      )

      // Mark as sent by transport layer
      messageStatusManager.markTransportSent(uiMessage.localId, transportResult)

      // Record message for rate limiting
      messageRateLimiter.recordMessage(uiMessage.transportMessage.content, contact.id)

      console.log('✅ Message sent via transport layer:', uiMessage.localId)

    } catch (error) {
      // Determine failure reason based on error
      let failureReason = MessageFailureReason.NETWORK_ERROR

      if (error.message.includes('conversation')) {
        failureReason = MessageFailureReason.CONVERSATION_ERROR
      } else if (error.message.includes('rate limit')) {
        failureReason = MessageFailureReason.RATE_LIMITED
      } else if (error.message.includes('blocked')) {
        failureReason = MessageFailureReason.BLOCKED_BY_USER
      }

      // Mark as failed by transport layer
      messageStatusManager.markTransportFailed(uiMessage.localId, error, failureReason)

      console.log('❌ Message failed at transport layer:', uiMessage.localId, error.message)

      // Don't throw error - let UI handle the failure state
    }
  }

  /**
   * Send typing indicator
   */
  async sendTypingIndicator(contact) {
    this._ensureInitialized()

    const options = this._buildMessageOptions(contact)
    return await this.provider.sendTypingIndicator(contact.id, options)
  }

  /**
   * Send typing end indicator
   */
  async sendTypingEnd(contact) {
    this._ensureInitialized()

    const options = this._buildMessageOptions(contact)
    return await this.provider.sendTypingEnd(contact.id, options)
  }

  /**
   * Retry a failed message
   */
  async retryMessage(localId) {
    this._ensureInitialized()

    console.log('🔄 [MessageService] Retrying message with localId:', localId)
    console.log('🔄 [MessageService] LocalId type:', typeof localId)

    let message = messageStatusManager.retryMessage(localId)

    // If message not found in status manager (e.g., after page refresh),
    // try to recreate it from chat store
    if (!message) {
      console.log('🔄 [MessageService] Message not in status manager, attempting to recreate...')
      const recreatedMessage = this._recreateMessageForRetry(localId)

      if (!recreatedMessage) {
        console.error('❌ [MessageService] Message not found in status manager or chat store')
        throw new Error('Message not found or cannot be retried')
      }

      // Now retry the recreated message
      message = messageStatusManager.retryMessage(localId)
      if (!message) {
        console.error('❌ [MessageService] Failed to retry recreated message')
        throw new Error('Failed to retry recreated message')
      }
    }

    // Find contact info from message
    const contact = this._findContactFromMessage(message)
    if (!contact) {
      throw new Error('Contact information not found for retry')
    }

    // Attempt to send again
    try {
      const options = this._buildMessageOptions(contact)
      const transportResult = await this.provider.sendChatMessage(
        message.transportMessage.to,
        message.transportMessage.content,
        options
      )

      // Mark as sent by transport layer
      messageStatusManager.markTransportSent(message.localId, transportResult)

      console.log('✅ Message retry successful:', message.localId)
      return message

    } catch (error) {
      // Determine failure reason
      let failureReason = MessageFailureReason.NETWORK_ERROR

      if (error.message.includes('conversation')) {
        failureReason = MessageFailureReason.CONVERSATION_ERROR
      } else if (error.message.includes('rate limit')) {
        failureReason = MessageFailureReason.RATE_LIMITED
      }

      // Mark as failed again
      messageStatusManager.markTransportFailed(message.localId, error, failureReason)

      console.log('❌ Message retry failed:', message.localId, error.message)
      throw error
    }
  }

  /**
   * Create a failed message for immediate UI feedback
   * This provides a unified way to create failed messages with consistent format
   */
  createFailedMessage(content, failureReason, canRetry = false) {
    const localId = `failed-${Date.now()}-${Math.random().toString(36).substring(2, 11)}`

    return {
      id: localId,
      localId,
      text: content,
      sender: 'self',
      timestamp: new Date(),
      status: MessageStatus.FAILED,
      failureReason,
      canRetry,
      // Add transport message structure for consistency
      transportMessage: {
        id: localId,
        type: MessageType.CHAT,
        from: this.currentUserId || 'unknown',
        to: 'unknown',
        content,
        timestamp: new Date().toISOString(),
        service: 1
      }
    }
  }

  /**
   * Get message status manager for external access
   */
  getStatusManager() {
    return messageStatusManager
  }

  /**
   * Handle incoming messages from provider
   */
  _handleMessage(message, conversation) {
    console.log('📨 [MessageService] Received message:', message.type, message.content)

    // Check if this is a system message
    if (message.type === MessageType.SYSTEM) {
      // Process system message for status management
      messageStatusManager.processSystemMessage(message)

      // Check if this is a displayable system message (no action field or action != 1)
      const hasAction = message.content && message.content.action === 1
      if (!hasAction) {
        // This is a displayable system message, emit it for UI display
        this._emitMessage(message, conversation)
      }
      // Status update messages (action: 1) are not displayed in chat UI
    } else {
      // Regular message
      this._emitMessage(message, conversation)
    }
  }

  /**
   * Handle incoming typing indicators from provider
   */
  _handleTyping(message, conversation) {
    console.log('⌨️ [MessageService] Received typing:', message.type)
    this._emitTyping(message, conversation)
  }

  /**
   * Emit message event for UI components
   */
  _emitMessage(message, conversation) {
    const event = new CustomEvent('chat-message-received', {
      detail: { message, conversation }
    })
    window.dispatchEvent(event)
  }

  /**
   * Emit typing event for UI components
   */
  _emitTyping(message, conversation) {
    const event = new CustomEvent('typing-message', {
      detail: { message, conversation }
    })
    window.dispatchEvent(event)
  }

  /**
   * Register message callback
   */
  onMessage(callback) {
    this._ensureInitialized()
    this.provider.onMessage(callback)
  }

  /**
   * Unregister message callback
   */
  offMessage(callback) {
    if (this.provider) {
      this.provider.offMessage(callback)
    }
  }

  /**
   * Register typing callback
   */
  onTyping(callback) {
    this._ensureInitialized()
    this.provider.onTyping(callback)
  }

  /**
   * Unregister typing callback
   */
  offTyping(callback) {
    if (this.provider) {
      this.provider.offTyping(callback)
    }
  }

  // Private methods

  /**
   * Ensure service is initialized
   */
  _ensureInitialized() {
    if (!this.isInitialized || !this.provider) {
      throw new Error('Message service not initialized')
    }
  }

  /**
   * Build message options based on contact info
   * Only includes generic contact information, provider-specific logic handled by provider
   */
  _buildMessageOptions(contact) {
    return {
      contactType: contact.contact_type
    }
  }

  /**
   * Recreate message for retry after page refresh
   */
  _recreateMessageForRetry(localId) {
    // Get chat store instance (assuming it's already initialized)
    const chatStore = this._getChatStore()
    if (!chatStore) {
      console.error('❌ [MessageService] Chat store not available')
      return null
    }

    // Find the message in chat store
    let foundMessage = null
    for (const chat of chatStore.chats) {
      if (chat.messages) {
        foundMessage = chat.messages.find(m => m.localId === localId)
        if (foundMessage) break
      }
    }

    if (!foundMessage || foundMessage.sender !== 'self') {
      return null
    }

    // Recreate the message object for status manager
    const recreatedMessage = {
      localId: foundMessage.localId,
      status: foundMessage.status || MessageStatus.FAILED,
      retryCount: foundMessage.retryCount || 0,
      failureReason: foundMessage.failureReason || MessageFailureReason.NETWORK_ERROR,
      providerError: foundMessage.providerError || 'Unknown error',
      systemMessage: foundMessage.systemMessage || null,
      canRetry: true,

      // Recreate transport message from UI message
      transportMessage: {
        id: foundMessage.localId,
        type: MessageType.CHAT,
        from: this.currentUserId,
        to: this._extractTargetFromMessage(foundMessage),
        content: foundMessage.text,
        timestamp: foundMessage.timestamp,
        service: 1
      },

      // UI fields
      text: foundMessage.text,
      sender: foundMessage.sender,
      timestamp: foundMessage.timestamp,
      messageType: MessageType.CHAT,
      isSystemMessage: false
    }

    // Register the recreated message in status manager
    messageStatusManager.pendingMessages.set(localId, recreatedMessage)
    console.log('✅ [MessageService] Recreated message for retry:', localId)

    // Important: Trigger an initial status change to ensure UI is in sync
    messageStatusManager._notifyStatusChange(recreatedMessage)

    return recreatedMessage
  }

  /**
   * Extract target entity from UI message by finding the chat it belongs to
   */
  _extractTargetFromMessage(foundMessage) {
    // Get chat store instance
    const chatStore = this._getChatStore()
    if (!chatStore) return 'unknown_target'

    // Find the chat that contains this message
    for (const chat of chatStore.chats) {
      if (chat.messages && chat.messages.some(m => m.localId === foundMessage.localId)) {
        return chat.entity_id // Return the chat's entity_id as the target
      }
    }

    // Fallback: try to extract from message content or use unknown
    return 'unknown_target'
  }

  /**
   * Get chat store instance safely
   */
  _getChatStore() {
    try {
      // Try to get the chat store from global state
      // This is a workaround to avoid circular dependency
      if (typeof window !== 'undefined' && window.__CHAT_STORE__) {
        return window.__CHAT_STORE__
      }
      return null
    } catch (error) {
      console.error('❌ [MessageService] Failed to get chat store:', error)
      return null
    }
  }

  /**
   * Find contact from message (for retry functionality)
   * Look up contact information from chat store
   */
  _findContactFromMessage(message) {
    // Get chat store instance
    const chatStore = this._getChatStore()
    if (!chatStore) {
      console.error('❌ [MessageService] Chat store not available for contact lookup')
      return null
    }

    // Find the contact by ID in chat store
    const targetId = message.transportMessage.to
    const chat = chatStore.chats.find(c => c.id === targetId)

    if (chat) {
      return {
        id: chat.id,
        contact_type: chat.contact_type
      }
    }

    console.error('❌ [MessageService] Contact not found in chat store:', targetId)
    return null
  }
}

// Create singleton instance
export const messageService = new MessageService()

// Export class for testing
export { MessageService }
