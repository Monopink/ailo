# 状态管理

## Pinia Store 架构

### Store 列表

- **authStore**: 用户认证和个人资料状态
- **chatStore**: 聊天列表和选中聊天状态
- **settingsStore**: 应用设置和配置

### Store 设计原则

- 保持Store专注和最小化
- 避免全局状态污染
- 使用组合式API风格
- 支持持久化存储

## 认证状态管理 (authStore)

### 状态定义

```javascript
// stores/auth.js
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useAuthStore = defineStore('auth', () => {
  // 状态
  const user = ref(null)
  const token = ref(localStorage.getItem('token'))
  const needsProfileSetup = ref(false)
  
  // 计算属性
  const isAuthenticated = computed(() => !!token.value)
  const userNickname = computed(() => user.value?.nickname || '')
  
  // 操作
  const login = async (credentials) => {
    const response = await apiClient.post('/auth/login', credentials)
    token.value = response.access_token
    localStorage.setItem('token', token.value)
    await fetchUserProfile()
  }
  
  const logout = () => {
    user.value = null
    token.value = null
    localStorage.removeItem('token')
    router.push('/login')
  }
  
  const fetchUserProfile = async () => {
    try {
      const response = await apiClient.get('/auth/me')
      user.value = response
      
      // 检查是否需要完善资料
      if (!response.nickname) {
        needsProfileSetup.value = true
      }
    } catch (error) {
      handleApiError(error, 'profile')
    }
  }
  
  return {
    user,
    token,
    needsProfileSetup,
    isAuthenticated,
    userNickname,
    login,
    logout,
    fetchUserProfile
  }
})
```

### 持久化策略

```javascript
// 自动持久化token
watch(token, (newToken) => {
  if (newToken) {
    localStorage.setItem('token', newToken)
  } else {
    localStorage.removeItem('token')
  }
})

// 应用启动时恢复状态
const initializeAuth = () => {
  const savedToken = localStorage.getItem('token')
  if (savedToken) {
    token.value = savedToken
    fetchUserProfile()
  }
}
```

## 聊天状态管理 (chatStore)

### 状态定义

```javascript
// stores/chat.js
export const useChatStore = defineStore('chat', () => {
  // 状态
  const contacts = ref([])
  const selectedChatId = ref(null)
  const messages = ref({}) // 按chatId组织的消息
  const contactLimits = ref({
    maxContacts: 10,
    currentCount: 0
  })
  
  // 计算属性
  const selectedContact = computed(() => {
    return contacts.value.find(c => c.id === selectedChatId.value)
  })
  
  const selectedMessages = computed(() => {
    return messages.value[selectedChatId.value] || []
  })
  
  const canAddMoreContacts = computed(() => {
    return contactLimits.value.currentCount < contactLimits.value.maxContacts
  })
  
  // 操作
  const fetchContacts = async () => {
    try {
      const response = await apiClient.get('/contacts')
      contacts.value = response.data
      contactLimits.value.currentCount = response.data.length
    } catch (error) {
      handleApiError(error, 'contacts')
    }
  }
  
  const selectChat = (chatId) => {
    selectedChatId.value = chatId
    // 更新联系人信息
    updateContactInfo(chatId)
  }
  
  const updateContactInfo = async (contactId) => {
    try {
      const response = await apiClient.get(`/contacts/${contactId}/chat-info`)
      const index = contacts.value.findIndex(c => c.id === contactId)
      if (index !== -1) {
        contacts.value[index] = { ...contacts.value[index], ...response.data }
      }
    } catch (error) {
      logger.error('Failed to update contact info', error)
    }
  }
  
  const addMessage = (message) => {
    const chatId = message.from === authStore.user?.id ? message.to : message.from
    if (!messages.value[chatId]) {
      messages.value[chatId] = []
    }
    messages.value[chatId].push(message)
  }
  
  const clearChatHistory = (chatId) => {
    messages.value[chatId] = []
    // 注意：不删除联系人，只清除消息历史
  }
  
  return {
    contacts,
    selectedChatId,
    messages,
    contactLimits,
    selectedContact,
    selectedMessages,
    canAddMoreContacts,
    fetchContacts,
    selectChat,
    updateContactInfo,
    addMessage,
    clearChatHistory
  }
})
```

### 消息状态管理

```javascript
// 消息状态枚举
const MessageStatus = {
  SENDING: 1,
  SENT: 2,
  FAILED: 3,
  BLOCKED: 4,
  DELIVERED: 5
}

// 消息失败重试
const retryMessage = async (messageId) => {
  const message = findMessageById(messageId)
  if (message && message.status === MessageStatus.FAILED) {
    message.status = MessageStatus.SENDING
    try {
      await sendMessage(message)
      message.status = MessageStatus.SENT
    } catch (error) {
      message.status = MessageStatus.FAILED
      handleApiError(error, 'message')
    }
  }
}
```

## 设置状态管理 (settingsStore)

### 状态定义

```javascript
// stores/settings.js
export const useSettingsStore = defineStore('settings', () => {
  // 状态
  const theme = ref('light')
  const notifications = ref(true)
  const language = ref('zh')
  const characterLimits = ref({
    nickname: 20,
    bio: 100,
    message: 1000
  })

  // 操作
  const updateSettings = (newSettings) => {
    Object.assign({
      theme: theme.value,
      notifications: notifications.value,
      language: language.value
    }, newSettings)
    saveToLocalStorage()
  }

  const saveToLocalStorage = () => {
    localStorage.setItem('settings', JSON.stringify({
      theme: theme.value,
      notifications: notifications.value,
      language: language.value
    }))
  }

  const loadFromLocalStorage = () => {
    const saved = localStorage.getItem('settings')
    if (saved) {
      const settings = JSON.parse(saved)
      theme.value = settings.theme || 'light'
      notifications.value = settings.notifications ?? true
      language.value = settings.language || 'zh'
    }
  }

  return {
    theme,
    notifications,
    language,
    characterLimits,
    updateSettings,
    loadFromLocalStorage
  }
})
```

## 数据持久化

### 本地存储策略

```javascript
// 聊天历史持久化
const saveChatHistory = () => {
  const chatData = {
    messages: messages.value,
    lastUpdate: Date.now()
  }
  localStorage.setItem('chatHistory', JSON.stringify(chatData))
}

// 恢复聊天历史
const loadChatHistory = () => {
  const saved = localStorage.getItem('chatHistory')
  if (saved) {
    const chatData = JSON.parse(saved)
    messages.value = chatData.messages || {}
  }
}
```

### 会话存储策略

```javascript
// 多账号支持的会话存储
const saveSessionData = (userId, data) => {
  const sessionKey = `session_${userId}`
  sessionStorage.setItem(sessionKey, JSON.stringify(data))
}

const loadSessionData = (userId) => {
  const sessionKey = `session_${userId}`
  const saved = sessionStorage.getItem(sessionKey)
  return saved ? JSON.parse(saved) : null
}
```

## Store 组合使用

### 跨Store通信

```javascript
// 在组件中使用多个Store
export default {
  setup() {
    const authStore = useAuthStore()
    const chatStore = useChatStore()
    
    // 监听认证状态变化
    watch(() => authStore.isAuthenticated, (isAuth) => {
      if (isAuth) {
        chatStore.fetchContacts()
      } else {
        chatStore.$reset() // 重置聊天状态
      }
    })
    
    return {
      authStore,
      chatStore
    }
  }
}
```

### 状态同步

```javascript
// 定期更新联系人信息
const ENABLE_PERIODIC_REFRESH = false // 可配置开关

if (ENABLE_PERIODIC_REFRESH) {
  setInterval(() => {
    if (authStore.isAuthenticated) {
      chatStore.fetchContacts()
    }
  }, 5 * 60 * 1000) // 5分钟
}
```

## 错误状态管理

### 全局错误处理

```javascript
// 在Store中统一处理错误
const handleStoreError = (error, context) => {
  logger.error(`Store error in ${context}`, error)
  
  // 根据错误类型处理
  if (error.status === 401) {
    authStore.logout()
  } else {
    handleApiError(error, context)
  }
}
```

### 加载状态管理

```javascript
// 加载状态跟踪
const loading = ref({
  contacts: false,
  messages: false,
  profile: false
})

const setLoading = (key, value) => {
  loading.value[key] = value
}
```
