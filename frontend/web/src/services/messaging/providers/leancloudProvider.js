/**
 * LeanCloud message provider implementation
 */

import { Realtime, TextMessage } from 'leancloud-realtime'
import { useToast } from 'vue-toastification'
import {
  createChatMessage,
  createTypingMessage,
  createTypingEndMessage,
  ContactType
} from '../types'

export class LeanCloudProvider {
  constructor() {
    this.currentUserId = null
    this.messageCallbacks = new Set()
    this.typingCallbacks = new Set()

    // LeanCloud connection management
    this.realtime = null
    this.client = null
    this.conversations = new Map() // Cache for conversations
    this.toast = useToast()
  }

  /**
   * Initialize the provider
   */
  async initialize(userId) {
    try {
      await this._initLeanCloud()
      await this._loginLeanCloud(userId)
      this.currentUserId = userId
      this._setupMessageHandlers()
      console.log('✅ LeanCloud provider initialized')
    } catch (error) {
      console.error('❌ Failed to initialize LeanCloud provider:', error)
      throw error
    }
  }

  /**
   * Initialize LeanCloud Realtime
   */
  async _initLeanCloud() {
    if (this.realtime) {
      console.log('✅ LeanCloud already initialized')
      return true
    }

    const maxRetries = 3
    let retries = 0
    let lastError = null

    try {
      const appId = import.meta.env.VITE_LEANCLOUD_APP_ID
      const appKey = import.meta.env.VITE_LEANCLOUD_APP_KEY
      const serverURL = import.meta.env.VITE_LEANCLOUD_SERVER_URL

      if (!appId || !appKey) {
        const error = new Error('LeanCloud appId and appKey are required')
        console.error('LeanCloud initialization failed:', error)
        this.toast.error('聊天服务初始化失败：缺少必要的配置信息')
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

      while (retries < maxRetries) {
        try {
          console.log(`Attempting to initialize LeanCloud (attempt ${retries + 1}/${maxRetries})...`)
          this.realtime = new Realtime(options)
          console.log('✅ LeanCloud Realtime initialized successfully')
          return true
        } catch (error) {
          if (error.message && error.message.includes('is already initialized')) {
            console.log('✅ LeanCloud already initialized (detected from error)')
            return true
          }

          lastError = error
          console.error(`LeanCloud initialization attempt ${retries + 1} failed:`, error)
          retries++

          if (retries < maxRetries) {
            const delay = retries * 1000
            console.log(`Retrying in ${delay}ms...`)
            await new Promise(resolve => setTimeout(resolve, delay))
          }
        }
      }

      console.error('LeanCloud Realtime initialization failed after multiple attempts:', lastError)
      this.toast.error('聊天服务初始化失败，请刷新页面重试')
      throw lastError

    } catch (error) {
      console.error('❌ Failed to initialize LeanCloud:', error)
      this.toast.error('聊天服务初始化失败')
      throw error
    }
  }

  /**
   * Login to LeanCloud with user ID
   */
  async _loginLeanCloud(userId) {
    try {
      if (!this.realtime) {
        await this._initLeanCloud()
      }

      if (!userId || typeof userId !== 'string') {
        console.error('Invalid userId type:', typeof userId)
        throw new Error('userId must be a string')
      }

      console.log(`Logging in to LeanCloud with user ID: ${userId}`)
      this.client = await this.realtime.createIMClient(userId.trim())
      this.currentUserId = userId.trim()

      console.log('✅ Successfully logged in to LeanCloud')
      return this.client
    } catch (error) {
      console.error('❌ Failed to login to LeanCloud:', error)
      this.toast.error('Chat service login failed, please try again')
      throw error
    }
  }

  /**
   * Cleanup the provider
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
      console.log('✅ LeanCloud provider cleaned up')
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

    const message = createChatMessage(this.currentUserId, targetId, content)

    try {
      if (options.contactType === ContactType.BOT && options.conversationId) {
        // Bot: Use system conversation
        await this._sendToSystemConversation(options.conversationId, message)
      } else {
        // User: Use regular conversation
        await this._sendToUserConversation(targetId, message)
      }

      console.log('✅ Chat message sent:', message.type)
      return message
    } catch (error) {
      console.error('❌ Failed to send chat message:', error)
      throw error
    }
  }

  /**
   * Send typing indicator
   */
  async sendTypingIndicator(targetId, options = {}) {
    if (!this.currentUserId) {
      throw new Error('Provider not initialized')
    }

    const message = createTypingMessage(this.currentUserId, targetId)

    try {
      if (options.contactType === ContactType.BOT && options.conversationId) {
        // Bot: Use system conversation
        await this._sendToSystemConversation(options.conversationId, message)
      } else {
        // User: Use regular conversation
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

    const message = createTypingEndMessage(this.currentUserId, targetId)

    try {
      if (options.contactType === ContactType.BOT && options.conversationId) {
        // Bot: Use system conversation
        await this._sendToSystemConversation(options.conversationId, message)
      } else {
        // User: Use regular conversation
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
              console.log('🔍 [LeanCloudProvider] Parsed structured message from _lctext:', parsedMessage)
            } catch (error) {
              console.error('❌ [LeanCloudProvider] Failed to parse _lctext:', {
                error: error.message,
                _lctext: messageContent._lctext,
                from: message.from
              })
              return
            }
          } else {
            // Direct structured message object
            parsedMessage = messageContent
            console.log('🔍 [LeanCloudProvider] Received structured message object:', parsedMessage)
          }
        } else if (typeof messageContent === 'string') {
          // Need to parse JSON string
          try {
            parsedMessage = JSON.parse(messageContent)
            console.log('🔍 [LeanCloudProvider] Parsed structured message from string:', parsedMessage)
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

        // Notify callbacks based on message type
        console.log('🔍 [LeanCloudProvider] Message type check:', {
          type: parsedMessage.type,
          isTyping: parsedMessage.type === 2,
          isTypingEnd: parsedMessage.type === 3,
          willUseTypingCallback: parsedMessage.type === 2 || parsedMessage.type === 3
        })

        if (parsedMessage.type === 2 || parsedMessage.type === 3) { // TYPING or TYPING_END
          console.log('🔍 [LeanCloudProvider] Sending to typing callbacks, count:', this.typingCallbacks.size)
          this.typingCallbacks.forEach(callback => {
            try {
              callback(parsedMessage, conversation)
            } catch (error) {
              console.error('Error in typing callback:', error)
            }
          })
        } else {
          console.log('🔍 [LeanCloudProvider] Sending to message callbacks, count:', this.messageCallbacks.size)
          this.messageCallbacks.forEach(callback => {
            try {
              callback(parsedMessage, conversation)
            } catch (error) {
              console.error('Error in message callback:', error)
            }
          })
        }
      } catch (error) {
        console.error('Error processing received message:', error)
      }
    })
  }
}
