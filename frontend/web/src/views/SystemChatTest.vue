<template>
  <div class="system-chat-test">
    <div class="header">
      <h1>系统对话测试</h1>
      <p>测试 LeanMessage 对话收发消息功能</p>
    </div>

    <div class="test-controls">
      <div class="bot-selector">
        <label>选择机器人:</label>
        <select v-model="selectedBot" @change="connectToBot">
          <option value="">请选择机器人</option>
          <option v-for="bot in bots" :key="bot.id" :value="bot">
            {{ bot.id }} ({{ bot.leancloud_conversation_id || '无对话ID' }})
          </option>
        </select>
      </div>

      <div class="connection-status">
        <span :class="['status', connectionStatus]">
          {{ connectionStatusText }}
        </span>
      </div>
    </div>

    <div class="chat-container" v-if="selectedBot">
      <div class="chat-header">
        <h3>与 {{ selectedBot.id }} 对话</h3>
        <p>对话ID: {{ selectedBot.leancloud_conversation_id }}</p>
      </div>

      <div class="messages" ref="messagesContainer">
        <div 
          v-for="message in messages" 
          :key="message.id"
          :class="['message', message.from === currentUserId ? 'sent' : 'received']"
        >
          <div class="message-content">
            <div class="text">{{ message.text }}</div>
            <div class="time">{{ formatTime(message.timestamp) }}</div>
          </div>
        </div>
      </div>

      <div class="input-area">
        <input 
          v-model="newMessage" 
          @keyup.enter="sendMessage"
          placeholder="输入消息..."
          :disabled="!isConnected"
        />
        <button @click="sendMessage" :disabled="!isConnected || !newMessage.trim()">
          发送
        </button>
      </div>
    </div>

    <div class="debug-info">
      <h3>调试信息</h3>
      <div class="debug-logs">
        <div v-for="log in debugLogs" :key="log.id" class="debug-log">
          <span class="timestamp">{{ formatTime(log.timestamp) }}</span>
          <span :class="['level', log.level]">{{ log.level }}</span>
          <span class="message">{{ log.message }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, nextTick } from 'vue'
import { useAuthStore } from '../stores/auth'
import { initLeanMessage, loginLeanMessage, connectToSystemConversation, sendMessageToSystemConversation, onMessage, getClientStatus } from '../services/leanmessage'

export default {
  name: 'SystemChatTest',
  setup() {
    const authStore = useAuthStore()
    // Remove the store reference as we'll use the service directly
    
    const bots = ref([])
    const selectedBot = ref(null)
    const messages = ref([])
    const newMessage = ref('')
    const debugLogs = ref([])
    const connectionStatus = ref('disconnected')
    const messagesContainer = ref(null)
    
    const currentUserId = ref('u1002') // Test user ID
    
    const connectionStatusText = computed(() => {
      switch (connectionStatus.value) {
        case 'connected': return '已连接'
        case 'connecting': return '连接中...'
        case 'disconnected': return '未连接'
        case 'error': return '连接错误'
        default: return '未知状态'
      }
    })
    
    const isConnected = computed(() => connectionStatus.value === 'connected')
    
    const addDebugLog = (level, message) => {
      debugLogs.value.unshift({
        id: Date.now(),
        timestamp: new Date(),
        level,
        message
      })
      // Keep only last 50 logs
      if (debugLogs.value.length > 50) {
        debugLogs.value = debugLogs.value.slice(0, 50)
      }
    }
    
    const loadBots = async () => {
      try {
        addDebugLog('INFO', '正在加载联系人列表...')
        
        // Get bots from contacts_service
        const response = await fetch('http://localhost:8002/admin/list-conversations')
        const data = await response.json()
        
        if (data.status === 'success') {
          // Filter system conversations and map to bot format
          const systemConversations = data.data.conversations.filter(conv => conv.sys)
          bots.value = systemConversations.map(conv => ({
            id: conv.name,
            leancloud_conversation_id: conv.objectId,
            nickname: conv.name,
            bio: conv.attr?.description || `Chat Contact - ${conv.name}`
          }))
          
          addDebugLog('SUCCESS', `加载了 ${bots.value.length} 个联系人`)
        } else {
          addDebugLog('ERROR', `加载联系人失败: ${data.message}`)
        }
      } catch (error) {
        addDebugLog('ERROR', `加载联系人错误: ${error.message}`)
      }
    }
    
    const connectToBot = async () => {
      if (!selectedBot.value) return
      
      try {
        connectionStatus.value = 'connecting'
        addDebugLog('INFO', `正在连接到联系人 ${selectedBot.value.id}...`)
        
        // Connect to LeanMessage with system conversation ID
        await connectToSystemConversation(selectedBot.value.leancloud_conversation_id)
        
        connectionStatus.value = 'connected'
        addDebugLog('SUCCESS', `已连接到系统对话 ${selectedBot.value.leancloud_conversation_id}`)
        
        // Clear previous messages
        messages.value = []
        
        // Listen for messages
        onMessage((message) => {
          addMessage(message.from, message.text, new Date())
          addDebugLog('RECEIVED', `收到消息: ${message.text}`)
        })
        
      } catch (error) {
        connectionStatus.value = 'error'
        addDebugLog('ERROR', `连接失败: ${error.message}`)
      }
    }
    
    const sendMessage = async () => {
      if (!newMessage.value.trim() || !isConnected.value) return
      
      try {
        const messageText = newMessage.value.trim()
        addDebugLog('SENDING', `发送消息: ${messageText}`)
        
        // Send message through LeanMessage
        await sendMessageToSystemConversation(selectedBot.value.leancloud_conversation_id, messageText)
        
        // Add to local messages
        addMessage(currentUserId.value, messageText, new Date())
        
        // Clear input
        newMessage.value = ''
        
        addDebugLog('SENT', '消息发送成功')
        
      } catch (error) {
        addDebugLog('ERROR', `发送消息失败: ${error.message}`)
      }
    }
    
    const addMessage = (from, text, timestamp) => {
      messages.value.push({
        id: Date.now() + Math.random(),
        from,
        text,
        timestamp
      })
      
      // Scroll to bottom
      nextTick(() => {
        if (messagesContainer.value) {
          messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
        }
      })
    }
    
    const formatTime = (date) => {
      return new Intl.DateTimeFormat('zh-CN', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
      }).format(date)
    }
    
    onMounted(async () => {
      try {
        // Check if LeanMessage is already initialized
        const status = getClientStatus()
        if (!status.isInitialized) {
          await initLeanMessage()
          addDebugLog('SUCCESS', 'LeanMessage 初始化成功')
        } else {
          addDebugLog('INFO', 'LeanMessage 已经初始化')
        }

        // Check if user is already logged in
        if (!status.isLoggedIn && currentUserId.value) {
          await loginLeanMessage(currentUserId.value)
          addDebugLog('SUCCESS', `用户 ${currentUserId.value} 登录成功`)
        } else if (status.isLoggedIn) {
          addDebugLog('INFO', `用户 ${status.currentUserId} 已经登录`)
        }

        loadBots()
        addDebugLog('INFO', '系统对话测试页面已加载')
      } catch (error) {
        addDebugLog('ERROR', `初始化失败: ${error.message}`)
      }
    })
    
    return {
      bots,
      selectedBot,
      messages,
      newMessage,
      debugLogs,
      connectionStatus,
      connectionStatusText,
      isConnected,
      currentUserId,
      messagesContainer,
      connectToBot,
      sendMessage,
      formatTime
    }
  }
}
</script>

<style scoped>
.system-chat-test {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
}

.header {
  text-align: center;
  margin-bottom: 30px;
}

.test-controls {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding: 15px;
  background: #f5f5f5;
  border-radius: 8px;
}

.bot-selector select {
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
  min-width: 300px;
}

.status {
  padding: 4px 12px;
  border-radius: 4px;
  font-weight: bold;
}

.status.connected { background: #d4edda; color: #155724; }
.status.connecting { background: #fff3cd; color: #856404; }
.status.disconnected { background: #f8d7da; color: #721c24; }
.status.error { background: #f8d7da; color: #721c24; }

.chat-container {
  border: 1px solid #ddd;
  border-radius: 8px;
  margin-bottom: 20px;
}

.chat-header {
  padding: 15px;
  background: #f8f9fa;
  border-bottom: 1px solid #ddd;
}

.messages {
  height: 400px;
  overflow-y: auto;
  padding: 15px;
}

.message {
  margin-bottom: 15px;
}

.message.sent .message-content {
  background: #95ec69;
  color: #1a1a1a;
  margin-left: auto;
  max-width: 70%;
}

.message.received .message-content {
  background: #e9ecef;
  color: #333;
  max-width: 70%;
}

.message-content {
  padding: 10px 15px;
  border-radius: 18px;
  display: inline-block;
}

.time {
  font-size: 0.8em;
  opacity: 0.7;
  margin-top: 5px;
}

.input-area {
  display: flex;
  padding: 15px;
  border-top: 1px solid #ddd;
}

.input-area input {
  flex: 1;
  padding: 10px;
  border: 1px solid #ddd;
  border-radius: 4px;
  margin-right: 10px;
}

.input-area button {
  padding: 10px 20px;
  background: #fdd700;
  color: #1a1a1a;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-weight: 500;
}

.input-area button:disabled {
  background: #6c757d;
  cursor: not-allowed;
}

.debug-info {
  background: #f8f9fa;
  border: 1px solid #ddd;
  border-radius: 8px;
  padding: 15px;
}

.debug-logs {
  max-height: 300px;
  overflow-y: auto;
  font-family: monospace;
  font-size: 0.9em;
}

.debug-log {
  margin-bottom: 5px;
  padding: 2px 0;
}

.timestamp {
  color: #666;
  margin-right: 10px;
}

.level {
  font-weight: bold;
  margin-right: 10px;
  padding: 2px 6px;
  border-radius: 3px;
}

.level.INFO { background: #d1ecf1; color: #0c5460; }
.level.SUCCESS { background: #d4edda; color: #155724; }
.level.ERROR { background: #f8d7da; color: #721c24; }
.level.SENDING { background: #fff3cd; color: #856404; }
.level.SENT { background: #d4edda; color: #155724; }
.level.RECEIVED { background: #e2e3e5; color: #383d41; }
</style>
