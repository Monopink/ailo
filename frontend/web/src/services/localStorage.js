// Local storage service for chat persistence with user-level isolation
import { compareMessageTimestamps } from '../utils/timeUtils'

const STORAGE_KEY_PREFIX = 'qiao'

// Generate user-specific storage keys
const getUserStorageKeys = (userId) => {
  if (!userId) {
    throw new Error('User ID is required for storage operations')
  }
  return {
    CHATS: `${STORAGE_KEY_PREFIX}_user_${userId}_chats`,
    USER_SETTINGS: `${STORAGE_KEY_PREFIX}_user_${userId}_settings`,
    LAST_SYNC: `${STORAGE_KEY_PREFIX}_user_${userId}_last_sync`,
    MESSAGE_STATUS: `${STORAGE_KEY_PREFIX}_user_${userId}_message_status`
  }
}

class LocalStorageService {
  constructor() {
    this.isSupported = this.checkSupport()
    this.currentUserId = null
    this.currentStorageKeys = null
  }

  checkSupport() {
    try {
      const test = '__localStorage_test__'
      localStorage.setItem(test, test)
      localStorage.removeItem(test)
      return true
    } catch (e) {
      console.warn('LocalStorage not supported:', e)
      return false
    }
  }

  /**
   * Set current user for storage operations
   * Must be called before any user-specific operations
   */
  setCurrentUser(userId) {
    if (!userId) {
      throw new Error('User ID cannot be null or empty')
    }
    this.currentUserId = userId
    this.currentStorageKeys = getUserStorageKeys(userId)
    console.log('LocalStorage: Set current user to', userId)
  }

  /**
   * Clear current user context
   */
  clearCurrentUser() {
    this.currentUserId = null
    this.currentStorageKeys = null
    console.log('LocalStorage: Cleared current user context')
  }

  /**
   * Get current user ID
   */
  getCurrentUserId() {
    return this.currentUserId
  }

  /**
   * Ensure user context is set for operations that require it
   */
  _ensureUserContext() {
    if (!this.currentUserId || !this.currentStorageKeys) {
      throw new Error('User context not set. Call setCurrentUser() first.')
    }
  }

  /**
   * Check if user context is available
   */
  _hasUserContext() {
    return !!(this.currentUserId && this.currentStorageKeys)
  }

  // Chat data management
  saveChats(chats) {
    if (!this.isSupported) return false
    this._ensureUserContext()

    try {
      const chatData = {
        chats: chats,
        timestamp: new Date().toISOString(),
        version: '2.0',
        userId: this.currentUserId // Add user verification
      }
      localStorage.setItem(this.currentStorageKeys.CHATS, JSON.stringify(chatData))
      console.log(`LocalStorage: Saved ${chats.length} chats for user ${this.currentUserId}`)
      return true
    } catch (e) {
      console.error('Failed to save chats to localStorage:', e)
      return false
    }
  }

  loadChats() {
    if (!this.isSupported) return null

    // Return null if no user context is set (user not logged in)
    if (!this._hasUserContext()) {
      console.log('LocalStorage: No user context set, returning null for loadChats')
      return null
    }

    try {
      const data = localStorage.getItem(this.currentStorageKeys.CHATS)
      if (!data) {
        console.log(`LocalStorage: No chat data found for user ${this.currentUserId}`)
        return null
      }

      const chatData = JSON.parse(data)

      // Validate data structure
      if (!chatData.chats || !Array.isArray(chatData.chats)) {
        console.warn('Invalid chat data structure in localStorage')
        return null
      }

      // Validate user ownership
      if (chatData.userId && chatData.userId !== this.currentUserId) {
        console.warn(`Chat data belongs to different user: ${chatData.userId}, current: ${this.currentUserId}`)
        return null
      }

      // Initialize unread count for existing chats if not present
      chatData.chats.forEach(chat => {
        if (typeof chat.unreadCount !== 'number') {
          chat.unreadCount = 0;
        }
      });

      console.log(`LocalStorage: Loaded ${chatData.chats.length} chats for user ${this.currentUserId}`)
      return {
        chats: chatData.chats,
        timestamp: chatData.timestamp,
        version: chatData.version || '1.0'
      }
    } catch (e) {
      console.error('Failed to load chats from localStorage:', e)
      return null
    }
  }

  // Individual chat management
  saveChat(chat) {
    this._ensureUserContext()
    const chatData = this.loadChats()
    if (!chatData) {
      return this.saveChats([chat])
    }

    const existingIndex = chatData.chats.findIndex(c => c.id === chat.id)
    if (existingIndex >= 0) {
      chatData.chats[existingIndex] = chat
    } else {
      chatData.chats.push(chat)
    }

    return this.saveChats(chatData.chats)
  }

  // Message management
  addMessage(chatId, message) {
    this._ensureUserContext()
    const chatData = this.loadChats()
    if (!chatData) return false

    const chat = chatData.chats.find(c => c.id === chatId)
    if (!chat) return false

    if (!chat.messages) {
      chat.messages = []
    }

    // Avoid duplicate messages - check both id and localId
    const existingMessage = chat.messages.find(m =>
      (m.id && message.id && m.id === message.id) ||
      (m.localId && message.localId && m.localId === message.localId)
    )

    if (!existingMessage) {
      const newMessage = {
        ...message,
        timestamp: message.timestamp || new Date().toISOString()
      };

      // Insert message at correct position based on timestamp
      let insertIndex = chat.messages.length; // Default to end

      // Find correct insertion position by comparing timestamps
      for (let i = chat.messages.length - 1; i >= 0; i--) {
        // Use compareMessageTimestamps for consistent sorting
        if (compareMessageTimestamps(newMessage, chat.messages[i]) >= 0) {
          insertIndex = i + 1;
          break;
        }
        insertIndex = i;
      }

      // Insert message at the correct position
      chat.messages.splice(insertIndex, 0, newMessage);

      // Keep only last 1000 messages per chat to avoid storage bloat
      if (chat.messages.length > 1000) {
        chat.messages = chat.messages.slice(-1000)
      }
    }

    return this.saveChats(chatData.chats)
  }

  // Message status management (new feature)
  saveMessageStatus(pendingMessages) {
    if (!this.isSupported) return false
    this._ensureUserContext()

    try {
      const statusData = {
        pendingMessages: pendingMessages || {},
        timestamp: new Date().toISOString(),
        version: '1.0',
        userId: this.currentUserId
      }
      localStorage.setItem(this.currentStorageKeys.MESSAGE_STATUS, JSON.stringify(statusData))
      console.log(`LocalStorage: Saved message status for user ${this.currentUserId}`)
      return true
    } catch (e) {
      console.error('Failed to save message status to localStorage:', e)
      return false
    }
  }

  loadMessageStatus() {
    if (!this.isSupported) return null

    // Return null if no user context is set (user not logged in)
    if (!this._hasUserContext()) {
      console.log('LocalStorage: No user context set, returning null for loadMessageStatus')
      return null
    }

    try {
      const data = localStorage.getItem(this.currentStorageKeys.MESSAGE_STATUS)
      if (!data) {
        console.log(`LocalStorage: No message status found for user ${this.currentUserId}`)
        return null
      }

      const statusData = JSON.parse(data)

      // Validate user ownership
      if (statusData.userId && statusData.userId !== this.currentUserId) {
        console.warn(`Message status belongs to different user: ${statusData.userId}, current: ${this.currentUserId}`)
        return null
      }

      console.log(`LocalStorage: Loaded message status for user ${this.currentUserId}`)
      return {
        pendingMessages: statusData.pendingMessages || {},
        timestamp: statusData.timestamp,
        version: statusData.version || '1.0'
      }
    } catch (e) {
      console.error('Failed to load message status from localStorage:', e)
      return null
    }
  }

  // User settings
  saveUserSettings(settings) {
    if (!this.isSupported) return false
    this._ensureUserContext()

    try {
      const settingsData = {
        ...settings,
        timestamp: new Date().toISOString(),
        userId: this.currentUserId
      }
      localStorage.setItem(this.currentStorageKeys.USER_SETTINGS, JSON.stringify(settingsData))
      console.log(`LocalStorage: Saved user settings for user ${this.currentUserId}`)
      return true
    } catch (e) {
      console.error('Failed to save user settings:', e)
      return false
    }
  }

  loadUserSettings() {
    if (!this.isSupported) return null

    // Return null if no user context is set (user not logged in)
    if (!this._hasUserContext()) {
      console.log('LocalStorage: No user context set, returning null for loadUserSettings')
      return null
    }

    try {
      const data = localStorage.getItem(this.currentStorageKeys.USER_SETTINGS)
      if (!data) return null

      const settingsData = JSON.parse(data)

      // Validate user ownership
      if (settingsData.userId && settingsData.userId !== this.currentUserId) {
        console.warn(`User settings belong to different user: ${settingsData.userId}, current: ${this.currentUserId}`)
        return null
      }

      return settingsData
    } catch (e) {
      console.error('Failed to load user settings:', e)
      return null
    }
  }

  // Sync management
  setLastSync(timestamp) {
    if (!this.isSupported) return false
    this._ensureUserContext()

    try {
      localStorage.setItem(this.currentStorageKeys.LAST_SYNC, timestamp)
      return true
    } catch (e) {
      console.error('Failed to save last sync timestamp:', e)
      return false
    }
  }

  getLastSync() {
    if (!this.isSupported) return null

    // Return null if no user context is set (user not logged in)
    if (!this._hasUserContext()) {
      console.log('LocalStorage: No user context set, returning null for getLastSync')
      return null
    }

    try {
      return localStorage.getItem(this.currentStorageKeys.LAST_SYNC)
    } catch (e) {
      console.error('Failed to get last sync timestamp:', e)
      return null
    }
  }

  // Cleanup and maintenance
  clearUserData() {
    if (!this.isSupported) return false
    this._ensureUserContext()

    try {
      Object.values(this.currentStorageKeys).forEach(key => {
        localStorage.removeItem(key)
      })
      console.log(`LocalStorage: Cleared all data for user ${this.currentUserId}`)
      return true
    } catch (e) {
      console.error('Failed to clear user localStorage:', e)
      return false
    }
  }

  // Clear all application data (all users) - use with caution
  clearAllData() {
    if (!this.isSupported) return false

    try {
      const keysToRemove = []
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i)
        if (key && key.startsWith(STORAGE_KEY_PREFIX)) {
          keysToRemove.push(key)
        }
      }

      keysToRemove.forEach(key => localStorage.removeItem(key))
      console.log(`LocalStorage: Cleared all application data (${keysToRemove.length} keys)`)
      return true
    } catch (e) {
      console.error('Failed to clear all localStorage:', e)
      return false
    }
  }

  getUserStorageSize() {
    if (!this.isSupported) return 0
    this._ensureUserContext()

    let total = 0
    try {
      Object.values(this.currentStorageKeys).forEach(key => {
        const data = localStorage.getItem(key)
        if (data) {
          total += data.length
        }
      })
    } catch (e) {
      console.error('Failed to calculate user storage size:', e)
    }

    return total
  }

  getAllStorageSize() {
    if (!this.isSupported) return 0

    let total = 0
    try {
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i)
        if (key && key.startsWith(STORAGE_KEY_PREFIX)) {
          const data = localStorage.getItem(key)
          if (data) {
            total += data.length
          }
        }
      }
    } catch (e) {
      console.error('Failed to calculate total storage size:', e)
    }

    return total
  }

  // Export/Import for backup
  exportUserData() {
    if (!this.isSupported) return null
    this._ensureUserContext()

    try {
      const data = {}
      Object.entries(this.currentStorageKeys).forEach(([name, key]) => {
        const value = localStorage.getItem(key)
        if (value) {
          data[name] = JSON.parse(value)
        }
      })

      return {
        ...data,
        exportTimestamp: new Date().toISOString(),
        exportUserId: this.currentUserId,
        version: '2.0'
      }
    } catch (e) {
      console.error('Failed to export user data:', e)
      return null
    }
  }

  importUserData(data) {
    if (!this.isSupported || !data) return false
    this._ensureUserContext()

    try {
      // Validate import data
      if (!data.version) {
        console.warn('Import data missing version')
        return false
      }

      // Validate user ownership if specified
      if (data.exportUserId && data.exportUserId !== this.currentUserId) {
        console.warn(`Import data belongs to different user: ${data.exportUserId}, current: ${this.currentUserId}`)
        // Allow import but warn user
      }

      // Import each data type
      if (data.CHATS) {
        localStorage.setItem(this.currentStorageKeys.CHATS, JSON.stringify(data.CHATS))
      }

      if (data.USER_SETTINGS) {
        localStorage.setItem(this.currentStorageKeys.USER_SETTINGS, JSON.stringify(data.USER_SETTINGS))
      }

      if (data.LAST_SYNC) {
        localStorage.setItem(this.currentStorageKeys.LAST_SYNC, data.LAST_SYNC)
      }

      if (data.MESSAGE_STATUS) {
        localStorage.setItem(this.currentStorageKeys.MESSAGE_STATUS, JSON.stringify(data.MESSAGE_STATUS))
      }

      console.log(`LocalStorage: Imported data for user ${this.currentUserId}`)
      return true
    } catch (e) {
      console.error('Failed to import user data:', e)
      return false
    }
  }

  // List all users with stored data
  listStoredUsers() {
    if (!this.isSupported) return []

    const users = new Set()
    try {
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i)
        if (key && key.startsWith(`${STORAGE_KEY_PREFIX}_user_`)) {
          const match = key.match(new RegExp(`^${STORAGE_KEY_PREFIX}_user_([^_]+)_`))
          if (match) {
            users.add(match[1])
          }
        }
      }
    } catch (e) {
      console.error('Failed to list stored users:', e)
    }

    return Array.from(users)
  }

  // Clear all chat messages for current user (keep contacts, clear messages only)
  clearAllChatMessages() {
    if (!this.isSupported) return false
    this._ensureUserContext()

    try {
      const chatData = this.loadChats()
      if (chatData && chatData.chats) {
        // Clear messages from all chats but keep chat structure
        chatData.chats.forEach(chat => {
          chat.messages = []
        })

        // Save updated chats
        this.saveChats(chatData.chats)
        console.log(`LocalStorage: Cleared all chat messages for user ${this.currentUserId}`)
        return true
      }
      return false
    } catch (e) {
      console.error('Failed to clear all chat messages:', e)
      return false
    }
  }

  // Clear messages for specific contact
  clearContactMessages(contactId) {
    if (!this.isSupported) return false
    this._ensureUserContext()

    try {
      const chatData = this.loadChats()
      if (chatData && chatData.chats) {
        const chat = chatData.chats.find(c => c.id === contactId)
        if (chat) {
          chat.messages = []
          this.saveChats(chatData.chats)
          console.log(`LocalStorage: Cleared messages for contact ${contactId} for user ${this.currentUserId}`)
          return true
        }
      }
      return false
    } catch (e) {
      console.error('Failed to clear contact messages:', e)
      return false
    }
  }
}

// Create singleton instance
const localStorageService = new LocalStorageService()

export default localStorageService
