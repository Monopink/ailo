<template>
  <div class="message-status-test">
    <div class="test-header">
      <h2>消息状态管理测试</h2>
      <p>测试消息发送失败重试和系统消息处理功能</p>
    </div>

    <div class="test-section">
      <h3>发送测试消息</h3>
      <div class="input-group">
        <input 
          v-model="testMessage" 
          placeholder="输入测试消息..." 
          @keyup.enter="sendTestMessage"
        />
        <button @click="sendTestMessage" :disabled="!testMessage.trim()">
          发送消息
        </button>
      </div>
    </div>

    <div class="test-section">
      <h3>模拟系统操作</h3>
      <div class="button-group">
        <button
          @click="simulateProviderFailure"
          :disabled="!selectedMessageId"
          class="btn-warning"
        >
          模拟发送失败
        </button>
        <button
          @click="simulateMessageBlock"
          :disabled="!selectedMessageId"
          class="btn-warning"
        >
          模拟消息被屏蔽
        </button>
        <button
          @click="simulateMessageDelivery"
          :disabled="!selectedMessageId"
          class="btn-success"
        >
          模拟消息送达
        </button>
        <button @click="clearMessages" class="btn-secondary">
          清除消息
        </button>
      </div>
      <p v-if="selectedMessageId" class="selected-message">
        已选择消息: {{ selectedMessageId }}
      </p>
    </div>

    <div class="test-section">
      <h3>消息列表</h3>
      <div class="message-list">
        <div 
          v-for="message in messages" 
          :key="message.localId"
          :class="[
            'test-message',
            `status-${message.status}`,
            { 'selected': selectedMessageId === message.localId }
          ]"
          @click="selectMessage(message.localId)"
        >
          <div class="message-header">
            <span class="message-id">{{ message.localId }}</span>
            <span class="message-status">状态: {{ getStatusText(message.status) }}</span>
          </div>
          <div class="message-content">{{ message.text }}</div>
          <div class="message-meta">
            <span>重试次数: {{ message.retryCount || 0 }}</span>
            <span v-if="message.errorMessage">错误: {{ message.errorMessage }}</span>
          </div>
          <div class="message-actions" v-if="message.status === MessageStatus.FAILED && message.canRetry">
            <button @click.stop="retryMessage(message.localId)" class="btn-retry">
              重新发送
            </button>
          </div>
        </div>
      </div>
    </div>

    <div class="test-section">
      <h3>状态管理器信息</h3>
      <div class="status-info">
        <p>待处理消息数量: {{ pendingMessagesCount }}</p>
        <button @click="refreshStatusInfo" class="btn-secondary">刷新信息</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { messageService } from '../services/messaging'
import { MessageStatus, MessageType, MessageFailureReason } from '../services/messaging/types'

// Reactive data
const testMessage = ref('')
const messages = ref([])
const selectedMessageId = ref(null)
const pendingMessagesCount = ref(0)

// Status text mapping
const statusTexts = {
  [MessageStatus.PENDING]: '发送中',
  [MessageStatus.SENT]: '已发送',
  [MessageStatus.FAILED]: '发送失败',
  [MessageStatus.BLOCKED]: '被屏蔽',
  [MessageStatus.DELIVERED]: '已送达'
}

// Methods
const getStatusText = (status) => {
  return statusTexts[status] || '未知状态'
}

const sendTestMessage = async () => {
  if (!testMessage.value.trim()) return

  try {
    // Create a mock contact for testing
    const mockContact = {
      entity_id: 'test_bot_001',
      contact_type: 2, // BOT
      name: '测试机器人'
    }

    const uiMessage = await messageService.sendChatMessage(mockContact, testMessage.value)
    messages.value.push(uiMessage)
    testMessage.value = ''
    
    console.log('✅ Test message sent:', uiMessage.localId)
  } catch (error) {
    console.error('❌ Failed to send test message:', error)
  }
}

const selectMessage = (localId) => {
  selectedMessageId.value = selectedMessageId.value === localId ? null : localId
}

const retryMessage = async (localId) => {
  try {
    await messageService.retryMessage(localId)
    console.log('✅ Message retry initiated:', localId)
  } catch (error) {
    console.error('❌ Failed to retry message:', error)
  }
}

const simulateProviderFailure = () => {
  if (!selectedMessageId.value) return

  // Simulate a provider failure
  const error = new Error('Network connection failed')
  messageService.getStatusManager().markTransportFailed(
    selectedMessageId.value,
    error,
    MessageFailureReason.NETWORK_ERROR
  )
  console.log('❌ Simulated provider failure for:', selectedMessageId.value)
}

const simulateMessageBlock = () => {
  if (!selectedMessageId.value) return

  // Simulate a system message that blocks the selected message
  const systemMessage = {
    type: MessageType.SYSTEM,
    content: `Message ${selectedMessageId.value} has been blocked by system policy`,
    from: 'system',
    to: 'user',
    timestamp: new Date().toISOString()
  }

  messageService.getStatusManager().processSystemMessage(systemMessage)
  console.log('🚫 Simulated message block for:', selectedMessageId.value)
}

const simulateMessageDelivery = () => {
  if (!selectedMessageId.value) return
  
  // Simulate a system message that confirms delivery
  const systemMessage = {
    type: MessageType.SYSTEM,
    content: `Message ${selectedMessageId.value} has been delivered successfully`,
    from: 'system',
    to: 'user',
    timestamp: new Date().toISOString()
  }
  
  messageService.getStatusManager().processSystemMessage(systemMessage)
  console.log('✅ Simulated message delivery for:', selectedMessageId.value)
}

const clearMessages = () => {
  messages.value = []
  selectedMessageId.value = null
  messageService.getStatusManager().clearCompletedMessages()
}

const refreshStatusInfo = () => {
  const statusManager = messageService.getStatusManager()
  pendingMessagesCount.value = statusManager.getPendingMessages().length
}

// Handle status changes
const handleStatusChange = (message) => {
  console.log('📊 Status changed:', message.localId, message.status)
  
  // Update message in list
  const index = messages.value.findIndex(m => m.localId === message.localId)
  if (index !== -1) {
    messages.value[index] = { ...messages.value[index], ...message }
  }
  
  refreshStatusInfo()
}

// Lifecycle
onMounted(() => {
  // Listen for status changes
  const statusManager = messageService.getStatusManager()
  statusManager.onStatusChange(handleStatusChange)
  
  refreshStatusInfo()
  console.log('🔧 Message status test page mounted')
})

onUnmounted(() => {
  // Clean up listeners
  const statusManager = messageService.getStatusManager()
  statusManager.offStatusChange(handleStatusChange)
  
  console.log('🔧 Message status test page unmounted')
})
</script>

<style scoped>
.message-status-test {
  max-width: 800px;
  margin: 0 auto;
  padding: 2rem;
}

.test-header {
  text-align: center;
  margin-bottom: 2rem;
}

.test-section {
  margin-bottom: 2rem;
  padding: 1rem;
  border: 1px solid var(--color-border);
  border-radius: var(--border-radius);
}

.input-group {
  display: flex;
  gap: 0.5rem;
}

.input-group input {
  flex: 1;
  padding: 0.5rem;
  border: 1px solid var(--color-border);
  border-radius: var(--border-radius-sm);
}

.button-group {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.btn-warning {
  background: var(--color-warning);
  color: white;
}

.btn-success {
  background: #28a745;
  color: white;
}

.btn-secondary {
  background: #6c757d;
  color: white;
}

.btn-retry {
  background: var(--color-primary);
  color: white;
  font-size: 0.8rem;
  padding: 0.25rem 0.5rem;
}

button {
  padding: 0.5rem 1rem;
  border: none;
  border-radius: var(--border-radius-sm);
  cursor: pointer;
  transition: opacity 0.2s;
}

button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.selected-message {
  margin-top: 0.5rem;
  font-size: 0.9rem;
  color: var(--color-text-secondary);
}

.message-list {
  max-height: 400px;
  overflow-y: auto;
}

.test-message {
  border: 1px solid var(--color-border);
  border-radius: var(--border-radius-sm);
  padding: 1rem;
  margin-bottom: 0.5rem;
  cursor: pointer;
  transition: all 0.2s;
}

.test-message:hover {
  background: var(--color-bg-secondary);
}

.test-message.selected {
  border-color: var(--color-primary);
  background: var(--color-accent-soft);
}

.test-message.status-1 { /* PENDING */
  border-left: 4px solid var(--color-primary);
}

.test-message.status-3 { /* FAILED */
  border-left: 4px solid var(--color-error);
}

.test-message.status-4 { /* BLOCKED */
  border-left: 4px solid var(--color-warning);
}

.test-message.status-5 { /* DELIVERED */
  border-left: 4px solid #28a745;
}

.message-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 0.5rem;
  font-size: 0.9rem;
}

.message-id {
  font-family: monospace;
  color: var(--color-text-secondary);
}

.message-status {
  font-weight: bold;
}

.message-content {
  margin-bottom: 0.5rem;
}

.message-meta {
  font-size: 0.8rem;
  color: var(--color-text-secondary);
  display: flex;
  gap: 1rem;
}

.message-actions {
  margin-top: 0.5rem;
}

.status-info {
  display: flex;
  align-items: center;
  gap: 1rem;
}
</style>
