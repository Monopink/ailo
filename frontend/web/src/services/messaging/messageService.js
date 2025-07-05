/**
 * Message service abstraction layer
 * Provides unified interface for different message providers
 */

import { LeanCloudProvider } from './providers/leancloudProvider'
import { ContactType } from './types'

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
      this.currentUserId = null
      this.isInitialized = false
      console.log('✅ Message service cleaned up')
    } catch (error) {
      console.error('❌ Failed to cleanup message service:', error)
    }
  }

  /**
   * Send a chat message
   * Automatically determines the conversation type based on contact info
   */
  async sendChatMessage(contact, content) {
    this._ensureInitialized()

    const options = this._buildMessageOptions(contact)
    return await this.provider.sendChatMessage(contact.entity_id, content, options)
  }

  /**
   * Send typing indicator
   */
  async sendTypingIndicator(contact) {
    this._ensureInitialized()

    const options = this._buildMessageOptions(contact)
    return await this.provider.sendTypingIndicator(contact.entity_id, options)
  }

  /**
   * Send typing end indicator
   */
  async sendTypingEnd(contact) {
    this._ensureInitialized()

    const options = this._buildMessageOptions(contact)
    return await this.provider.sendTypingEnd(contact.entity_id, options)
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
   */
  _buildMessageOptions(contact) {
    const options = {
      contactType: contact.contact_type
    }

    // For bots, include conversation ID
    if (contact.contact_type === ContactType.BOT) {
      options.conversationId = contact.leancloud_conversation_id
    }

    return options
  }
}

// Create singleton instance
export const messageService = new MessageService()

// Export class for testing
export { MessageService }
