// Local storage service for chat persistence

const STORAGE_KEYS = {
  CHATS: 'says_chats',
  USER_SETTINGS: 'says_user_settings',
  LAST_SYNC: 'says_last_sync'
}

class LocalStorageService {
  constructor() {
    this.isSupported = this.checkSupport()
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

  // Chat data management
  saveChats(chats) {
    if (!this.isSupported) return false
    
    try {
      const chatData = {
        chats: chats,
        timestamp: new Date().toISOString(),
        version: '1.0'
      }
      localStorage.setItem(STORAGE_KEYS.CHATS, JSON.stringify(chatData))
      return true
    } catch (e) {
      console.error('Failed to save chats to localStorage:', e)
      return false
    }
  }

  loadChats() {
    if (!this.isSupported) return null
    
    try {
      const data = localStorage.getItem(STORAGE_KEYS.CHATS)
      if (!data) return null
      
      const chatData = JSON.parse(data)
      
      // Validate data structure
      if (!chatData.chats || !Array.isArray(chatData.chats)) {
        console.warn('Invalid chat data structure in localStorage')
        return null
      }
      
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
    const chatData = this.loadChats()
    if (!chatData) return false
    
    const chat = chatData.chats.find(c => c.id === chatId)
    if (!chat) return false
    
    if (!chat.messages) {
      chat.messages = []
    }
    
    // Avoid duplicate messages
    const existingMessage = chat.messages.find(m => m.id === message.id)
    if (!existingMessage) {
      chat.messages.push({
        ...message,
        timestamp: message.timestamp || new Date().toISOString()
      })
      
      // Keep only last 1000 messages per chat to avoid storage bloat
      if (chat.messages.length > 1000) {
        chat.messages = chat.messages.slice(-1000)
      }
    }
    
    return this.saveChats(chatData.chats)
  }

  // User settings
  saveUserSettings(settings) {
    if (!this.isSupported) return false
    
    try {
      localStorage.setItem(STORAGE_KEYS.USER_SETTINGS, JSON.stringify(settings))
      return true
    } catch (e) {
      console.error('Failed to save user settings:', e)
      return false
    }
  }

  loadUserSettings() {
    if (!this.isSupported) return null
    
    try {
      const data = localStorage.getItem(STORAGE_KEYS.USER_SETTINGS)
      return data ? JSON.parse(data) : null
    } catch (e) {
      console.error('Failed to load user settings:', e)
      return null
    }
  }

  // Sync management
  setLastSync(timestamp) {
    if (!this.isSupported) return false
    
    try {
      localStorage.setItem(STORAGE_KEYS.LAST_SYNC, timestamp)
      return true
    } catch (e) {
      console.error('Failed to save last sync timestamp:', e)
      return false
    }
  }

  getLastSync() {
    if (!this.isSupported) return null
    
    try {
      return localStorage.getItem(STORAGE_KEYS.LAST_SYNC)
    } catch (e) {
      console.error('Failed to get last sync timestamp:', e)
      return null
    }
  }

  // Cleanup and maintenance
  clearAllData() {
    if (!this.isSupported) return false
    
    try {
      Object.values(STORAGE_KEYS).forEach(key => {
        localStorage.removeItem(key)
      })
      return true
    } catch (e) {
      console.error('Failed to clear localStorage:', e)
      return false
    }
  }

  getStorageSize() {
    if (!this.isSupported) return 0
    
    let total = 0
    try {
      Object.values(STORAGE_KEYS).forEach(key => {
        const data = localStorage.getItem(key)
        if (data) {
          total += data.length
        }
      })
    } catch (e) {
      console.error('Failed to calculate storage size:', e)
    }
    
    return total
  }

  // Export/Import for backup
  exportData() {
    if (!this.isSupported) return null
    
    try {
      const data = {}
      Object.entries(STORAGE_KEYS).forEach(([name, key]) => {
        const value = localStorage.getItem(key)
        if (value) {
          data[name] = JSON.parse(value)
        }
      })
      
      return {
        ...data,
        exportTimestamp: new Date().toISOString(),
        version: '1.0'
      }
    } catch (e) {
      console.error('Failed to export data:', e)
      return null
    }
  }

  importData(data) {
    if (!this.isSupported || !data) return false
    
    try {
      // Validate import data
      if (!data.version) {
        console.warn('Import data missing version')
        return false
      }
      
      // Import each data type
      if (data.CHATS) {
        localStorage.setItem(STORAGE_KEYS.CHATS, JSON.stringify(data.CHATS))
      }
      
      if (data.USER_SETTINGS) {
        localStorage.setItem(STORAGE_KEYS.USER_SETTINGS, JSON.stringify(data.USER_SETTINGS))
      }
      
      if (data.LAST_SYNC) {
        localStorage.setItem(STORAGE_KEYS.LAST_SYNC, data.LAST_SYNC)
      }
      
      return true
    } catch (e) {
      console.error('Failed to import data:', e)
      return false
    }
  }
}

// Create singleton instance
const localStorageService = new LocalStorageService()

export default localStorageService
