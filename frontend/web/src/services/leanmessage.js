import { Realtime, TextMessage, Event } from 'leancloud-realtime'
import { createMessage, createTypingMessage, createTypingEndMessage, validateMessage, MessageType } from '../utils/messageTypes'
import { useToast } from 'vue-toastification'

let realtime = null
let client = null
let currentUserId = null
let conversations = new Map() // Cache for conversations

// Initialize toast service
const toast = useToast()

// Initialize LeanMessage Realtime
export async function initLeanMessage() {
  // Maximum retry attempts
  const maxRetries = 3
  let retries = 0
  let lastError = null

  try {
    const appId = import.meta.env.VITE_LEANCLOUD_APP_ID
    const appKey = import.meta.env.VITE_LEANCLOUD_APP_KEY
    const serverURL = import.meta.env.VITE_LEANCLOUD_SERVER_URL

    if (!appId || !appKey) {
      const error = new Error('LeanMessage appId and appKey are required')
      console.error('LeanMessage initialization failed:', error)
      toast.error('聊天服务初始化失败：缺少必要的配置信息')
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
      console.log('Using LeanMessage region: CN')
    } else if (serverURL === 'US') {
      options.server = 'https://rtm-router.leancloud.app'
      console.log('Using LeanMessage region: US')
    } else if (serverURL) {
      options.server = serverURL
      console.log(`Using LeanMessage server URL: ${serverURL}`)
    } else {
      console.warn('No LeanMessage region or server URL provided. This may cause issues for CN region apps.')
    }

    // Log initialization options (hide sensitive info)
    console.log('LeanMessage initialization options:', {
      appId: options.appId,
      appKey: options.appKey ? '******' : undefined,
      server: options.server
    })

    while (retries < maxRetries) {
      try {
        console.log(`Attempting to initialize LeanMessage (attempt ${retries + 1}/${maxRetries})...`)

        realtime = new Realtime(options)
        console.log('✅ LeanMessage Realtime initialized successfully')
        return true // Success, exit function
      } catch (error) {
        lastError = error
        console.error(`LeanMessage initialization attempt ${retries + 1} failed:`, error)
        retries++

        if (retries < maxRetries) {
          // Wait before retry
          const delay = retries * 1000 // 1s, 2s, 3s...
          console.log(`Retrying in ${delay}ms...`)
          await new Promise(resolve => setTimeout(resolve, delay))
        }
      }
    }

    // All retries failed
    console.error('LeanMessage Realtime initialization failed after multiple attempts:', lastError)
    toast.error('聊天服务初始化失败，请刷新页面重试')
    throw lastError

  } catch (error) {
    console.error('❌ Failed to initialize LeanMessage:', error)
    toast.error('聊天服务初始化失败')
    throw error
  }
}

// Login to LeanMessage with user ID
export async function loginLeanMessage(userId) {
  try {
    if (!realtime) {
      await initLeanMessage()
    }

    if (!userId || typeof userId !== 'string') {
      console.error('Invalid userId type:', typeof userId)
      throw new Error('userId must be a string')
    }

    console.log(`Logging in to LeanMessage with user ID: ${userId}`)
    client = await realtime.createIMClient(userId.trim())
    currentUserId = userId.trim()

    // Setup event handlers
    setupClientEventHandlers()

    console.log('✅ Successfully logged in to LeanMessage')
    return client
  } catch (error) {
    console.error('❌ Failed to login to LeanMessage:', error)
    toast.error('Chat service login failed, please try again')
    throw error
  }
}

// Logout from LeanMessage
export async function logoutLeanMessage() {
  try {
    if (client) {
      await client.close()
      client = null
      currentUserId = null
      conversations.clear()
      console.log('✅ Successfully logged out from LeanMessage')
    }
  } catch (error) {
    console.error('❌ Failed to logout from LeanMessage:', error)
  }
}

// Setup client event handlers
function setupClientEventHandlers() {
  if (!client) return

  // Listen for connection state changes
  client.on(Event.DISCONNECT, () => {
    console.log('LeanMessage client disconnected')
    toast.warning('Chat service disconnected, attempting to reconnect...')
  })

  client.on(Event.RECONNECT, () => {
    console.log('LeanMessage client reconnected')
    toast.success('Chat service reconnected')
  })

  client.on(Event.RECONNECT_ERROR, (error) => {
    console.error('LeanMessage client reconnect failed:', error)
    toast.error('Chat service reconnection failed, please refresh the page')
  })
}

// Get or create a conversation
export async function getOrCreateConversation(targetUserId, conversationName = null) {
  try {
    if (!client) {
      throw new Error('Not logged in to LeanMessage')
    }

    // Check cache first
    const cacheKey = `${currentUserId}-${targetUserId}`
    if (conversations.has(cacheKey)) {
      console.log('Found cached conversation:', conversations.get(cacheKey).id)
      return conversations.get(cacheKey)
    }

    // Try to find existing conversation
    const query = client.getQuery()
    const existingConversations = await query
      .equalTo('members', [currentUserId, targetUserId])
      .find()

    if (existingConversations.length > 0) {
      console.log('Found existing conversation:', existingConversations[0].id)
      const conversation = existingConversations[0]
      conversations.set(cacheKey, conversation)
      setupConversationEventHandlers(conversation)
      return conversation
    }

    // Create new conversation
    const conversation = await client.createConversation({
      members: [currentUserId, targetUserId],
      name: conversationName || `Chat with ${targetUserId}`,
      unique: true
    })

    console.log('Created new conversation:', conversation.id)
    conversations.set(cacheKey, conversation)
    setupConversationEventHandlers(conversation)
    return conversation
  } catch (error) {
    console.error('❌ Failed to get or create conversation:', error)
    toast.error('Failed to create or get conversation')
    throw error
  }
}

// Setup conversation event handlers
function setupConversationEventHandlers(conversation) {
  if (!conversation) return

  // Listen for member changes
  conversation.on(Event.MEMBERS_JOIN, (payload) => {
    console.log('Members joined:', payload.members)
  })

  conversation.on(Event.MEMBERS_LEFT, (payload) => {
    console.log('Members left:', payload.members)
  })
}

// Connect to system conversation by conversation ID
export async function connectToSystemConversation(conversationId) {
  try {
    if (!client) {
      throw new Error('Not logged in to LeanMessage')
    }

    // Check cache first
    if (conversations.has(conversationId)) {
      console.log('Found cached system conversation:', conversationId)
      return conversations.get(conversationId)
    }

    console.log(`Connecting to system conversation: ${conversationId}`)
    const conversation = await client.getConversation(conversationId)

    // Cache the conversation
    conversations.set(conversationId, conversation)
    setupConversationEventHandlers(conversation)

    console.log('✅ Connected to system conversation:', conversation.id)
    return conversation
  } catch (error) {
    console.error('❌ Failed to connect to system conversation:', error)
    toast.error('Failed to connect to system conversation')
    throw error
  }
}

// Send a message to system conversation
export async function sendMessageToSystemConversation(conversationId, messageText) {
  try {
    if (!client) {
      throw new Error('Not logged in to LeanMessage')
    }

    const conversation = await connectToSystemConversation(conversationId)

    // For system conversations, send plain text message (not structured JSON)
    const textMessage = new TextMessage(messageText)
    const message = await conversation.send(textMessage)

    console.log('✅ Message sent to system conversation:', message.id)
    return message
  } catch (error) {
    console.error('❌ Failed to send message to system conversation:', error)
    toast.error('Failed to send message to system conversation')
    throw error
  }
}

// Send a message (legacy function for backward compatibility)
export async function sendMessage(targetUserId, messageText) {
  try {
    if (!client) {
      throw new Error('Not logged in to LeanMessage')
    }

    const conversation = await getOrCreateConversation(targetUserId)

    // Create structured message using utility function
    const messageContent = createMessage(currentUserId, targetUserId, messageText)

    // Validate message structure
    const validation = validateMessage(messageContent)
    if (!validation.isValid) {
      throw new Error(`Invalid message: ${validation.errors.join(', ')}`)
    }

    // Create TextMessage with structured content
    const textMessage = new TextMessage(JSON.stringify(messageContent))
    const message = await conversation.send(textMessage)

    console.log('✅ Message sent successfully:', message.id)
    return message
  } catch (error) {
    console.error('❌ Failed to send message:', error)
    toast.error('Failed to send message')
    throw error
  }
}

// Send message to specific conversation by ID
export async function sendMessageToConversation(conversationId, content) {
  try {
    if (!client) {
      throw new Error('Not logged in to LeanMessage')
    }

    let conversation = conversations.get(conversationId)

    // Get conversation if not in cache
    if (!conversation) {
      try {
        conversation = await client.getConversation(conversationId)
        conversations.set(conversationId, conversation)
        setupConversationEventHandlers(conversation)
      } catch (error) {
        console.error('Failed to get conversation:', error)
        toast.error('Failed to get conversation')
        throw error
      }
    }

    // Create text message
    const message = new TextMessage(content)

    // Send message
    const result = await conversation.send(message)
    console.log('Message sent:', result)
    return result
  } catch (error) {
    console.error('Failed to send message:', error)
    toast.error('Failed to send message')
    throw error
  }
}

// Send typing indicator
export async function sendTypingIndicator(targetUserId) {
  try {
    if (!client) {
      throw new Error('Not logged in to LeanMessage')
    }

    const conversation = await getOrCreateConversation(targetUserId)
    const typingMessage = createTypingMessage(currentUserId, targetUserId)
    const textMessage = new TextMessage(JSON.stringify(typingMessage))

    await conversation.send(textMessage)
    console.log('✅ Typing indicator sent')
  } catch (error) {
    console.error('❌ Failed to send typing indicator:', error)
  }
}

// Send typing end indicator
export async function sendTypingEndIndicator(targetUserId) {
  try {
    if (!client) {
      throw new Error('Not logged in to LeanMessage')
    }

    const conversation = await getOrCreateConversation(targetUserId)
    const typingEndMessage = createTypingEndMessage(currentUserId, targetUserId)
    const textMessage = new TextMessage(JSON.stringify(typingEndMessage))

    await conversation.send(textMessage)
    console.log('✅ Typing end indicator sent')
  } catch (error) {
    console.error('❌ Failed to send typing end indicator:', error)
  }
}

// Get conversation history messages
export async function getHistoryMessages(conversationId, options = {}) {
  try {
    if (!client) {
      throw new Error('Not logged in to LeanMessage')
    }

    let conversation = conversations.get(conversationId)

    // Get conversation if not in cache
    if (!conversation) {
      try {
        conversation = await client.getConversation(conversationId)
        conversations.set(conversationId, conversation)
        setupConversationEventHandlers(conversation)
      } catch (error) {
        console.error('Failed to get conversation:', error)
        toast.error('Failed to get conversation')
        throw error
      }
    }

    // Get history messages
    const messages = await conversation.queryMessages({
      limit: options.limit || 20,
      timestamp: options.timestamp
    })

    console.log('History messages:', messages)
    return messages
  } catch (error) {
    console.error('Failed to get history messages:', error)
    toast.error('Failed to get history messages')
    throw error
  }
}

// Listen for incoming messages
export function onMessage(callback) {
  if (!client) {
    console.warn('Not logged in to LeanMessage, cannot listen for messages')
    return
  }

  client.on('message', (message, conversation) => {
    console.log('📨 Received message:', message.text, 'from:', message.from)

    // Try to parse structured message content
    let parsedMessage = message
    try {
      const messageData = JSON.parse(message.text)

      // Validate the parsed message
      const validation = validateMessage(messageData)
      if (validation.isValid) {
        // This is a valid structured message
        parsedMessage = {
          ...message,
          text: messageData.content || '', // Extract the actual text content
          messageData: messageData, // Keep the full structured data
          messageType: messageData.message_type,
          isTyping: messageData.message_type === MessageType.TYPING.code,
          isTypingEnd: messageData.message_type === MessageType.TYPING_END.code,
          isSystem: messageData.message_type === MessageType.SYSTEM.code,
          isContent: [MessageType.CHAT.code, MessageType.CHAT_NOTYPING.code].includes(messageData.message_type)
        }
      } else {
        console.warn('Invalid structured message:', validation.errors)
        // Treat as plain text message
        parsedMessage = {
          ...message,
          text: message.text,
          messageData: null,
          messageType: MessageType.CHAT.code,
          isContent: true
        }
      }
    } catch (e) {
      // If parsing fails, treat as plain text message
      console.log('Plain text message received')
      parsedMessage = {
        ...message,
        text: message.text,
        messageData: null,
        messageType: MessageType.CHAT.code,
        isContent: true
      }
    }

    callback(parsedMessage, conversation)
  })
}

// Remove message listener
export function offMessage(callback) {
  if (client) {
    client.off('message', callback)
  }
}

// Get current client status
export function getClientStatus() {
  return {
    isInitialized: !!realtime,
    isLoggedIn: !!client,
    currentUserId: currentUserId
  }
}

// Export client for advanced usage
export function getClient() {
  return client
}

// Legacy function names for backward compatibility
export const initLeanCloud = initLeanMessage
export const loginLeanCloud = loginLeanMessage
export const logoutLeanCloud = logoutLeanMessage
