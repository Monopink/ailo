/**
 * LeanCloud message provider implementation
 */

import { Realtime, TextMessage, MessageQueryDirection } from 'leancloud-realtime'
import { useToast } from 'vue-toastification'
import {
  createChatMessage,
  createTypingMessage,
  createTypingEndMessage,
  ContactType
} from '../types'
import { messageEncryption } from '../../encryption/messageEncryption'
import { multiDeviceManager } from '../multiDeviceManager'
import { smartRetryStrategy } from '../smartRetryStrategy'
import { conversationErrorReporter } from '../conversationErrorReporter'

// Global Realtime instance singleton with persistence
class RealtimeSingleton {
  constructor() {
    this.instance = null
  }

  getInstance() {
    return this.instance
  }

  setInstance(instance) {
    this.instance = instance
  }

  clearInstance() {
    this.instance = null
  }
}

const realtimeSingleton = new RealtimeSingleton()

export class LeanCloudProvider {
  constructor() {
    this.currentUserId = null
    this.messageCallbacks = new Set()
    this.typingCallbacks = new Set()
    this.messageEncryption = messageEncryption

    // LeanCloud connection management
    this.realtime = null
    this.client = null
    this.conversations = new Map() // Cache for conversations
    this.toast = useToast()

    // Conversation ID caching
    this.unifiedConversationId = null
    this.conversationIdPromise = null
  }

  /**
   * Static method to reset global Realtime instance (for testing/debugging)
   */
  static resetGlobalInstance() {
    realtimeSingleton.clearInstance()
    console.log('🔄 Global LeanCloud instance reset')
  }

  /**
   * Initialize the provider
   */
  async initialize(userId) {
    try {
      console.log('🔄 Initializing LeanCloud provider...')

      await this._initLeanCloud()
      await this._loginLeanCloud(userId)
      this.currentUserId = userId
      this._setupMessageHandlers()

      // Preload unified conversation ID (non-blocking)
      this._preloadConversationId()

      console.log('✅ LeanCloud provider initialized successfully')
    } catch (error) {
      console.error('❌ Failed to initialize LeanCloud provider:', error)
      this.toast.error('服务初始化失败，请刷新页面重试')
      throw error
    }
  }

  /**
   * Initialize LeanCloud Realtime using singleton pattern
   */
  async _initLeanCloud() {
    // Check if we already have a global instance
    const existingInstance = realtimeSingleton.getInstance()
    if (existingInstance) {
      this.realtime = existingInstance
      console.log('✅ Using existing global LeanCloud instance')
      return
    }

    // Check if this instance already has realtime
    if (this.realtime) {
      realtimeSingleton.setInstance(this.realtime)
      console.log('✅ LeanCloud already initialized on this instance')
      return
    }

    // Get configuration
    const appId = import.meta.env.VITE_LEANCLOUD_APP_ID
    const appKey = import.meta.env.VITE_LEANCLOUD_APP_KEY
    const serverURL = import.meta.env.VITE_LEANCLOUD_SERVER_URL

    if (!appId || !appKey) {
      const error = new Error('LeanCloud appId and appKey are required')
      console.error('LeanCloud initialization failed:', error)
      this.toast.error('聊天服务初始化失败')
      throw error
    }

    const options = {
      appId,
      appKey,
      debug: true
    }

    // Configure server based on region
    if (serverURL === 'CN') {
      options.server = 'https://zcuk19lc.lc-cn-n1-shared.com'
      console.log('Using LeanCloud region: CN')
    } else if (serverURL === 'US') {
      options.server = 'https://rtm-router.leancloud.app'
      console.log('Using LeanCloud region: US')
    } else if (serverURL) {
      options.server = serverURL
      console.log(`Using LeanCloud server URL: ${serverURL}`)
    }

    console.log('LeanCloud initialization options:', {
      appId: options.appId,
      appKey: options.appKey ? '******' : undefined,
      server: options.server
    })

    try {
      console.log('Attempting to initialize LeanCloud...')

      // Try to create new Realtime instance
      const newRealtime = new Realtime(options)

      // Verify initialization
      if (!newRealtime) {
        throw new Error('Realtime instance is null after initialization')
      }

      // Set both instance and global reference
      this.realtime = newRealtime
      realtimeSingleton.setInstance(newRealtime)

      console.log('✅ LeanCloud Realtime initialized successfully')
    } catch (error) {
      if (error.message && error.message.includes('is already initialized')) {
        console.log('⚠️ LeanCloud already initialized, trying to find existing instance...')

        // If there's a global instance, use it
        const existingInstance = realtimeSingleton.getInstance()
        if (existingInstance) {
          this.realtime = existingInstance
          console.log('✅ Using existing global LeanCloud instance')
          return
        }

        // If no global instance but error says already initialized,
        // there might be a dangling instance somewhere
        console.error('❌ LeanCloud says already initialized but no global instance found')
        throw new Error('LeanCloud initialization conflict: already initialized but no accessible instance')
      } else {
        console.error('❌ LeanCloud initialization failed:', error)
        throw error
      }
    }
  }

  /**
   * Login to LeanCloud with user ID
   */
  async _loginLeanCloud(userId) {
    // Convert userId to string if it's not already
    if (!userId) {
      console.error('userId is required')
      throw new Error('userId is required')
    }

    // Ensure userId is a string
    userId = String(userId)

    try {
      if (!this.realtime) {
        await this._initLeanCloud()
      }

      // Double-check realtime instance is functional
      if (!this.realtime || typeof this.realtime.createIMClient !== 'function') {
        console.warn('⚠️ Realtime instance is not functional, reinitializing...')
        this.realtime = null
        await this._initLeanCloud()
      }

      console.log(`🔄 Logging in to LeanCloud with user ID: ${userId}`)

      // Get login options from multi-device manager
      const loginOptions = multiDeviceManager.getLoginOptions(userId)

      console.log('🔧 [LeanCloudProvider] Using login options:', loginOptions)

      // Create IM client with multi-device support
      this.client = await this.realtime.createIMClient(userId.trim(), loginOptions)
      this.currentUserId = userId.trim()

      console.log('✅ Successfully logged in to LeanCloud')
      return this.client
    } catch (error) {
      console.error('❌ LeanCloud login failed:', error)

      // Close any partial client connection
      if (this.client) {
        try {
          await this.client.close()
        } catch (closeError) {
          console.warn('⚠️ Error closing client after failed login:', closeError)
        }
        this.client = null
      }

      throw error
    }
  }

  /**
   * Cleanup the provider (but keep global realtime instance)
   */
  async cleanup() {
    try {
      if (this.client) {
        await this.client.close()
        this.client = null
      }
      this.currentUserId = null
      this.conversations.clear()
      this.messageCallbacks.clear()
      this.typingCallbacks.clear()

      // Don't clear this.realtime or globalRealtimeInstance
      // They should be reused across provider instances

      console.log('✅ LeanCloud provider cleaned up (keeping global realtime instance)')
    } catch (error) {
      console.error('❌ Failed to cleanup LeanCloud provider:', error)
    }
  }



  /**
   * Send a chat message
   */
  async sendChatMessage(targetId, content, options = {}) {
    if (!this.currentUserId) {
      throw new Error('Provider not initialized')
    }

    // Ensure targetId is a string
    targetId = String(targetId)

    // Create message object with provided ID if available
    const message = createChatMessage(this.currentUserId, targetId, content)

    // Use provided message ID if available, otherwise keep the generated one
    if (options.messageId) {
      message.id = options.messageId
    }

    // Encrypt message at provider level
    const encryptedMessage = this.messageEncryption.encryptMessage(message)

    // Generate unique message ID for retry tracking
    const messageId = `${targetId}_${Date.now()}_${Math.random().toString(36).substring(2, 11)}`
    let retryCount = 0

    const attemptSend = async () => {
      try {
        if (options.contactType === ContactType.TYPE2) {
          // TYPE2: Use unified system conversation
          const conversationId = await this._getUnifiedConversationId()
          await this._sendToSystemConversation(conversationId, encryptedMessage)

          // Update conversation health on success
          smartRetryStrategy.updateConversationHealth(conversationId, true)
        } else {
          // TYPE1: Use regular conversation
          await this._sendToUserConversation(targetId, encryptedMessage)
        }

        console.log('✅ Chat message sent:', encryptedMessage.type)
        return encryptedMessage
      } catch (error) {
        console.error(`❌ Failed to send chat message (attempt ${retryCount + 1}):`, error)

        // Update conversation health on error
        if (options.contactType === ContactType.TYPE2) {
          try {
            const conversationId = await this._getUnifiedConversationId()
            smartRetryStrategy.updateConversationHealth(conversationId, false, {
              error: error.message,
              timestamp: Date.now()
            })
          } catch (e) {
            // Ignore errors getting conversation ID for health update
          }
        }

        // Check if we should retry using smart strategy
        const retryDecision = smartRetryStrategy.shouldRetry(messageId, error, retryCount)

        if (retryDecision.shouldRetry) {
          console.log(`🔄 Smart retry decision: ${retryDecision.reason}`)

          // Clear conversation cache for conversation-related errors
          if (error.message.includes('conversation') || error.message.includes('404') || error.message.includes('not configured')) {
            this.clearConversationIdCache()
          }

          retryCount++

          // Execute retry with smart strategy
          const conversationId = options.contactType === ContactType.TYPE2 ?
            await this._getUnifiedConversationId().catch(() => 'unknown') : targetId

          return await smartRetryStrategy.executeRetry(
            messageId,
            attemptSend,
            retryDecision,
            conversationId
          )
        } else {
          console.log(`❌ Not retrying: ${retryDecision.reason}`)
          throw error
        }
      }
    }

    return await attemptSend()
  }

  /**
   * Send typing indicator
   */
  async sendTypingIndicator(targetId, options = {}) {
    if (!this.currentUserId) {
      throw new Error('Provider not initialized')
    }

    // Ensure targetId is a string
    targetId = String(targetId)

    const message = createTypingMessage(this.currentUserId, targetId)

    try {
      if (options.contactType === ContactType.TYPE2) {
        // TYPE2: Use system conversation (all TYPE2 messages go through unified conversation)
        const conversationId = await this._getUnifiedConversationId()
        await this._sendToSystemConversation(conversationId, message)
      } else {
        // TYPE1: Use regular conversation
        await this._sendToUserConversation(targetId, message)
      }

      console.log('✅ Typing indicator sent')
      return message
    } catch (error) {
      console.error('❌ Failed to send typing indicator:', error)
      throw error
    }
  }

  /**
   * Send typing end indicator
   */
  async sendTypingEnd(targetId, options = {}) {
    if (!this.currentUserId) {
      throw new Error('Provider not initialized')
    }

    // Ensure targetId is a string
    targetId = String(targetId)

    const message = createTypingEndMessage(this.currentUserId, targetId)

    try {
      if (options.contactType === ContactType.TYPE2) {
        // TYPE2: Use system conversation (all TYPE2 messages go through unified conversation)
        const conversationId = await this._getUnifiedConversationId()
        await this._sendToSystemConversation(conversationId, message)
      } else {
        // TYPE1: Use regular conversation
        await this._sendToUserConversation(targetId, message)
      }

      console.log('✅ Typing end sent')
      return message
    } catch (error) {
      console.error('❌ Failed to send typing end:', error)
      throw error
    }
  }

  /**
   * Register message callback
   */
  onMessage(callback) {
    this.messageCallbacks.add(callback)
  }

  /**
   * Unregister message callback
   */
  offMessage(callback) {
    this.messageCallbacks.delete(callback)
  }

  /**
   * Register typing callback
   */
  onTyping(callback) {
    this.typingCallbacks.add(callback)
  }

  /**
   * Unregister typing callback
   */
  offTyping(callback) {
    this.typingCallbacks.delete(callback)
  }

  // Private methods

  /**
   * Send message to system conversation
   */
  async _sendToSystemConversation(conversationId, message) {
    const conversation = await this._connectToSystemConversation(conversationId)
    if (!conversation) {
      throw new Error('Failed to connect to system conversation')
    }

    const textMessage = new TextMessage(JSON.stringify(message))
    await conversation.send(textMessage)
  }

  /**
   * Send message to user conversation
   */
  async _sendToUserConversation(targetId, message) {
    const conversation = await this._getOrCreateConversation(targetId)
    if (!conversation) {
      throw new Error('Failed to get or create user conversation')
    }

    const textMessage = new TextMessage(JSON.stringify(message))
    await conversation.send(textMessage, {
      receipt: conversation.members.length === 2
    })
  }

  /**
   * Connect to system conversation
   */
  async _connectToSystemConversation(conversationId) {
    try {
      if (!this.client) {
        throw new Error('Not logged in to LeanCloud')
      }

      // Check cache first
      if (this.conversations.has(conversationId)) {
        return this.conversations.get(conversationId)
      }

      console.log(`Connecting to system conversation: ${conversationId}`)
      const conversation = await this.client.getConversation(conversationId)

      // Cache the conversation
      this.conversations.set(conversationId, conversation)

      console.log('✅ Connected to system conversation')
      return conversation
    } catch (error) {
      console.error('❌ Failed to connect to system conversation:', error)
      throw error
    }
  }

  /**
   * Get or create user conversation
   */
  async _getOrCreateConversation(targetUserId) {
    try {
      if (!this.client) {
        throw new Error('Not logged in to LeanCloud')
      }

      // Ensure targetUserId is a string
      targetUserId = String(targetUserId)

      // Check cache first
      const cacheKey = `user_${targetUserId}`
      if (this.conversations.has(cacheKey)) {
        return this.conversations.get(cacheKey)
      }

      console.log(`Getting or creating conversation with user: ${targetUserId}`)

      // Try to find existing conversation
      const query = this.client.getQuery()
        .containsMembers([this.currentUserId, targetUserId])
        .limit(1)

      const conversations = await query.find()

      let conversation
      if (conversations.length > 0) {
        conversation = conversations[0]
        console.log('✅ Found existing conversation')
      } else {
        // Create new conversation
        conversation = await this.client.createConversation({
          members: [this.currentUserId, targetUserId],
          unique: true
        })
        console.log('✅ Created new conversation')
      }

      // Cache the conversation
      this.conversations.set(cacheKey, conversation)

      return conversation
    } catch (error) {
      console.error('❌ Failed to get or create conversation:', error)
      throw error
    }
  }

  /**
   * Setup message handlers
   */
  _setupMessageHandlers() {
    if (!this.client) {
      console.error('❌ No LeanCloud client available for message handling')
      return
    }

    console.log('✅ [LeanCloudProvider] Setting up direct message handlers')

    this.client.on('message', (message, conversation) => {
      try {
        console.log('📨 [LeanCloudProvider] Raw message received:', {
          content: message.content,
          from: message.from,
          conversation: conversation.id
        })

        // Get message content from the correct field
        const messageContent = message.content || message.text || ''

        // Handle structured message - could be object or JSON string
        let parsedMessage
        if (typeof messageContent === 'object' && messageContent !== null) {
          // Check if it's a LeanCloud TextMessage with _lctext
          if (messageContent._lctext) {
            try {
              parsedMessage = JSON.parse(messageContent._lctext)
            } catch (error) {
              console.error('❌ [LeanCloudProvider] Failed to parse _lctext:', {
                error: error.message,
                from: message.from
              })
              return
            }
          } else {
            // Direct structured message object
            parsedMessage = messageContent
          }
        } else if (typeof messageContent === 'string') {
          // Need to parse JSON string
          try {
            parsedMessage = JSON.parse(messageContent)

          } catch (error) {
            console.error('❌ [LeanCloudProvider] Failed to parse structured message:', {
              error: error.message,
              messageContent,
              from: message.from
            })
            // Skip invalid messages that don't follow structured format
            return
          }
        } else {
          console.error('❌ [LeanCloudProvider] Invalid message content type:', {
            type: typeof messageContent,
            messageContent,
            from: message.from
          })
          return
        }

        // Route message to appropriate callbacks based on type
        if (parsedMessage.type === 2 || parsedMessage.type === 3) { // TYPING or TYPING_END
          this.typingCallbacks.forEach(callback => {
            try {
              callback(parsedMessage, conversation)
            } catch (error) {
              console.error('Error in typing callback:', error)
            }
          })
        } else {
          // Decrypt message at provider level before passing to callbacks
          const decryptedMessage = this.messageEncryption.decryptMessage(parsedMessage)

          this.messageCallbacks.forEach(callback => {
            try {
              callback(decryptedMessage, conversation)
            } catch (error) {
              console.error('Error in message callback:', error)
            }
          })
        }
      } catch (error) {
        console.error('Error processing received message:', error)
      }
    })

    // Handle unread messages count update (for offline messages)
    this.client.on('unreadmessagescountupdate', (conversations) => {
      console.log('📬 [LeanCloud] Received unread messages update for', conversations.length, 'conversations')

      for (let conv of conversations) {
        console.log(`📬 [LeanCloud] Conversation ${conv.id}: ${conv.unreadMessagesCount} unread messages`)

        // If there are unread messages, fetch them
        if (conv.unreadMessagesCount > 0) {
          this._fetchOfflineMessages(conv)
        }
      }
    })

    // Handle login conflicts using multi-device manager
    this.client.on('conflict', (conflictInfo) => {
      console.warn('⚠️ [LeanCloud] Login conflict detected - user logged in on another device')

      // Delegate to multi-device manager for handling
      multiDeviceManager.handleLoginConflict({
        source: 'leancloud',
        userId: this.currentUserId,
        deviceInfo: multiDeviceManager.getDeviceInfo(),
        timestamp: new Date().toISOString(),
        ...conflictInfo
      })
    })

    // Handle network status changes for multi-device scenarios
    this._setupNetworkHandlers()
  }

  /**
   * Fetch offline messages for a conversation
   */
  async _fetchOfflineMessages(conversation) {
    try {
      console.log(`📬 [LeanCloud] Fetching ${conversation.unreadMessagesCount} offline messages for conversation ${conversation.id}`)

      // Query messages from the conversation
      const messages = await conversation.queryMessages({
        limit: Math.min(conversation.unreadMessagesCount, 50), // Limit to prevent too many messages at once
        direction: MessageQueryDirection.NEW_TO_OLD // Get newest messages first
      })

      console.log(`📬 [LeanCloud] Retrieved ${messages.length} offline messages`)

      // Process messages in chronological order (oldest first)
      // Filter out typing messages and other non-chat messages
      const chatMessages = messages.filter(msg => {
        try {
          const content = msg.content || msg.text || ''
          let parsedMessage

          if (typeof content === 'object' && content !== null) {
            if (content._lctext) {
              parsedMessage = JSON.parse(content._lctext)
            } else {
              parsedMessage = content
            }
          } else if (typeof content === 'string') {
            parsedMessage = JSON.parse(content)
          } else {
            return false
          }

          // Only include chat messages (type 1), exclude typing (type 2, 3) and system (type 9)
          return parsedMessage.type === 1
        } catch (error) {
          console.warn('Failed to parse message for filtering:', error)
          return false
        }
      })

      console.log(`📬 [LeanCloud] Filtered ${chatMessages.length} chat messages from ${messages.length} total messages`)

      for (const message of chatMessages.reverse()) {
        this._handleOfflineMessage(message, conversation)
      }

      // Mark conversation as read to clear unread count
      await conversation.read()
      console.log(`✅ [LeanCloud] Marked conversation ${conversation.id} as read`)

    } catch (error) {
      console.error('❌ [LeanCloud] Failed to fetch offline messages:', error)
    }
  }

  /**
   * Handle a single offline message
   */
  _handleOfflineMessage(message, conversation) {
    try {
      // Get message content
      const messageContent = message.content || message.text || ''

      // Parse structured message
      let parsedMessage
      if (typeof messageContent === 'object' && messageContent !== null) {
        if (messageContent._lctext) {
          try {
            parsedMessage = JSON.parse(messageContent._lctext)
          } catch (error) {
            console.error('❌ [LeanCloud] Failed to parse offline message _lctext:', error)
            return
          }
        } else {
          parsedMessage = messageContent
        }
      } else if (typeof messageContent === 'string') {
        try {
          parsedMessage = JSON.parse(messageContent)
        } catch (error) {
          console.error('❌ [LeanCloud] Failed to parse offline message JSON:', error)
          return
        }
      } else {
        console.error('❌ [LeanCloud] Invalid offline message content type:', typeof messageContent)
        return
      }



      // Decrypt message
      const decryptedMessage = this.messageEncryption.decryptMessage(parsedMessage)

      // Mark as offline message for proper timestamp handling
      decryptedMessage.source = 'offline'

      // Forward to message callbacks
      this.messageCallbacks.forEach(callback => {
        try {
          callback(decryptedMessage, conversation)
        } catch (error) {
          console.error('Error in offline message callback:', error)
        }
      })

      console.log('📬 [LeanCloud] Processed offline message from:', parsedMessage.from)

    } catch (error) {
      console.error('❌ [LeanCloud] Error processing offline message:', error)
    }
  }

  /**
   * Get unified system conversation ID with caching
   */
  async _getUnifiedConversationId() {
    // Return cached value if available
    if (this.unifiedConversationId) {
      return this.unifiedConversationId
    }

    // Prevent concurrent requests
    if (this.conversationIdPromise) {
      return await this.conversationIdPromise
    }

    // Fetch conversation ID from API
    this.conversationIdPromise = this._fetchConversationId()

    try {
      this.unifiedConversationId = await this.conversationIdPromise
      return this.unifiedConversationId
    } catch (error) {
      console.error('Failed to get unified conversation ID:', error)
      throw error
    } finally {
      this.conversationIdPromise = null
    }
  }

  /**
   * Fetch conversation ID from backend API
   */
  async _fetchConversationId() {
    const response = await fetch('/api/v1/system/conversation-id', {
      headers: {
        'Content-Type': 'application/json'
      }
    })

    if (!response.ok) {
      if (response.status === 404) {
        throw new Error('Conversation not configured. Please run setup tools.')
      }
      throw new Error(`Failed to get conversation ID: ${response.status}`)
    }

    const data = await response.json()
    return data.conversation_id
  }

  /**
   * Preload conversation ID in background (non-blocking)
   */
  async _preloadConversationId() {
    try {
      await this._getUnifiedConversationId()
      console.log('✅ Conversation ID preloaded')
    } catch (error) {
      console.warn('⚠️ Failed to preload conversation ID:', error)
      // Don't block initialization, will retry when actually needed
    }
  }

  /**
   * Clear conversation ID cache (for error recovery)
   */
  clearConversationIdCache() {
    this.unifiedConversationId = null
    this.conversationIdPromise = null
    console.log('🔄 Conversation ID cache cleared')
  }

  /**
   * Setup network status handlers for multi-device scenarios
   */
  _setupNetworkHandlers() {
    if (!this.realtime) {
      console.warn('⚠️ [LeanCloudProvider] No realtime instance for network handlers')
      return
    }

    // Connection status events
    this.realtime.on('disconnect', () => {
      console.log('🔌 [LeanCloud] Disconnected from server')
      this._emitNetworkEvent('disconnect')
    })

    this.realtime.on('offline', () => {
      console.log('📴 [LeanCloud] Network offline')
      this._emitNetworkEvent('offline')
    })

    this.realtime.on('online', () => {
      console.log('📶 [LeanCloud] Network online')
      this._emitNetworkEvent('online')
    })

    this.realtime.on('schedule', (attempt, delay) => {
      console.log(`⏰ [LeanCloud] Scheduled reconnect attempt ${attempt + 1} in ${delay}ms`)
      this._emitNetworkEvent('schedule', { attempt, delay })
    })

    this.realtime.on('retry', (attempt) => {
      console.log(`🔄 [LeanCloud] Reconnect attempt ${attempt + 1}`)
      this._emitNetworkEvent('retry', { attempt })
    })

    this.realtime.on('reconnect', () => {
      console.log('✅ [LeanCloud] Reconnected to server')
      this._emitNetworkEvent('reconnect')
    })

    console.log('✅ [LeanCloudProvider] Network handlers setup complete')
  }

  /**
   * Emit network event for UI components
   */
  _emitNetworkEvent(type, data = {}) {
    const event = new CustomEvent('messaging-network-status', {
      detail: {
        type,
        data,
        deviceInfo: multiDeviceManager.getDeviceInfo(),
        timestamp: new Date().toISOString()
      }
    })
    window.dispatchEvent(event)
  }
}
