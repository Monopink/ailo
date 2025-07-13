<template>
  <Teleport to="body">
    <div v-if="show" class="modal-overlay" @click="handleOverlayClick">
      <div class="modal-content developer-info-modal" @click.stop>
        <div class="modal-header">
          <h3>开发者信息</h3>
          <button @click="$emit('close')" class="close-btn" aria-label="关闭">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
              <path d="M18 6L6 18M6 6l12 12" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </button>
        </div>

        <div class="modal-body">
          <!-- Environment Info -->
          <div class="info-section">
            <h4>环境信息</h4>
            <div class="info-grid">
              <div class="info-item">
                <span class="label">环境:</span>
                <span class="value">{{ isDev ? '开发' : '生产' }}</span>
              </div>
              <div class="info-item">
                <span class="label">版本:</span>
                <span class="value">{{ appVersion }}</span>
              </div>
              <div class="info-item">
                <span class="label">用户ID:</span>
                <span class="value">{{ currentUserId || '未登录' }}</span>
              </div>
            </div>
          </div>

          <!-- Multi-Device Info -->
          <div class="info-section">
            <h4>多端登录</h4>
            <div class="info-grid">
              <div class="info-item">
                <span class="label">设备类型:</span>
                <span class="value">{{ getDeviceTypeLabel(deviceInfo.type) }}</span>
              </div>
              <div class="info-item">
                <span class="label">设备标记:</span>
                <span class="value">{{ deviceInfo.deviceTag || '无限制' }}</span>
              </div>
              <div class="info-item">
                <span class="label">登录策略:</span>
                <span class="value">{{ getStrategyLabel(deviceInfo.loginStrategy) }}</span>
              </div>
              <div class="info-item">
                <span class="label">会话ID:</span>
                <span class="value">{{ deviceInfo.sessionId }}</span>
              </div>
            </div>
          </div>

          <!-- Network Status -->
          <div class="info-section">
            <h4>网络状态</h4>
            <div class="info-grid">
              <div class="info-item">
                <span class="label">连接状态:</span>
                <span class="value" :class="networkStatusClass">{{ networkStatus }}</span>
              </div>
              <div class="info-item">
                <span class="label">最后更新:</span>
                <span class="value">{{ lastNetworkUpdate }}</span>
              </div>
            </div>
          </div>

          <!-- Message Service Status -->
          <div class="info-section">
            <h4>消息服务</h4>
            <div class="info-grid">
              <div class="info-item">
                <span class="label">服务状态:</span>
                <span class="value" :class="messageServiceStatusClass">{{ messageServiceStatus }}</span>
              </div>
              <div class="info-item">
                <span class="label">提供商:</span>
                <span class="value">LeanCloud</span>
              </div>
            </div>
          </div>

          <!-- Recent Events -->
          <div class="info-section">
            <h4>测试事件</h4>
            <div class="events-list">
              <div v-for="event in recentEvents" :key="event.id" class="event-item">
                <span class="event-time">{{ formatTime(event.timestamp) }}</span>
                <span class="event-type" :class="`event-${event.type}`">{{ event.type }}</span>
                <span class="event-message">{{ event.message }}</span>
              </div>
              <div v-if="recentEvents.length === 0" class="no-events">
                暂无事件
              </div>
            </div>
          </div>

          <!-- Test Actions -->
          <div class="info-section">
            <h4>测试操作</h4>
            <div class="actions">
              <button @click="refreshStatus" class="btn btn-secondary">刷新状态</button>
              <button @click="clearEvents" class="btn btn-secondary">清除事件</button>
              <button @click="testMessage" class="btn btn-secondary">测试消息</button>
              <button @click="exportStatus" class="btn btn-primary">导出数据</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { multiDeviceManager } from '../services/messaging/multiDeviceManager'
import { messageService } from '../services/messaging/messageService'
import { useAuthStore } from '../stores/auth'
import { DeviceTypeLabels } from '../services/messaging/types'

// Props
const props = defineProps({
  show: {
    type: Boolean,
    default: false
  }
})

// Emits
const emit = defineEmits(['close'])

const authStore = useAuthStore()

// Reactive data
const deviceInfo = reactive({})
const networkStatus = ref('未知')
const messageServiceStatus = ref('未知')
const lastNetworkUpdate = ref('--')
const recentEvents = ref([])

let eventListeners = []

// Computed properties
const isDev = computed(() => import.meta.env.DEV)
const appVersion = computed(() => {
  const version = import.meta.env.VITE_APP_VERSION
  if (!version) {
    throw new Error('VITE_APP_VERSION environment variable is required but not set')
  }
  return version
})
const currentUserId = computed(() => authStore.user?.id || null)

const refreshStatus = () => {
  Object.assign(deviceInfo, multiDeviceManager.getDeviceInfo())

  // Check message service status
  if (messageService.isInitialized) {
    messageServiceStatus.value = '已连接'
  } else {
    messageServiceStatus.value = '未连接'
  }

  addEvent('refresh', '状态已刷新')
}

const clearEvents = () => {
  recentEvents.value = []
  addEvent('clear', '事件已清除')
}

const testMessage = () => {
  addEvent('test', '测试消息功能')
  // Add test message logic here if needed
}

const exportStatus = () => {
  const status = {
    environment: {
      isDev: isDev.value,
      version: appVersion.value,
      userId: currentUserId.value
    },
    deviceInfo: deviceInfo,
    networkStatus: networkStatus.value,
    messageServiceStatus: messageServiceStatus.value,
    lastNetworkUpdate: lastNetworkUpdate.value,
    recentEvents: recentEvents.value,
    timestamp: new Date().toISOString()
  }

  const blob = new Blob([JSON.stringify(status, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `dev-test-data-${Date.now()}.json`
  a.click()
  URL.revokeObjectURL(url)

  addEvent('export', '测试数据已导出')
}

const addEvent = (type, message) => {
  const event = {
    id: Date.now(),
    type,
    message,
    timestamp: new Date()
  }
  
  recentEvents.value.unshift(event)
  
  // Keep only last 10 events
  if (recentEvents.value.length > 10) {
    recentEvents.value = recentEvents.value.slice(0, 10)
  }
}

const getDeviceTypeLabel = (deviceType) => {
  return DeviceTypeLabels[deviceType] || '未知'
}

const getStrategyLabel = (strategy) => {
  switch (strategy) {
    case 'unlimited':
      return '无限制多端'
    case 'single':
      return '单设备'
    case 'limited':
      return '限制多端'
    default:
      return '未知'
  }
}

const networkStatusClass = computed(() => {
  switch (networkStatus.value) {
    case '已连接':
      return 'status-connected'
    case '已断开':
      return 'status-disconnected'
    case '重连中':
      return 'status-reconnecting'
    default:
      return 'status-unknown'
  }
})

const messageServiceStatusClass = computed(() => {
  switch (messageServiceStatus.value) {
    case '已连接':
      return 'status-connected'
    case '未连接':
      return 'status-disconnected'
    default:
      return 'status-unknown'
  }
})

const formatTime = (timestamp) => {
  return new Date(timestamp).toLocaleTimeString()
}

// Setup event listeners
const setupEventListeners = () => {
  // Network status events
  const networkHandler = (event) => {
    const { type, data } = event.detail
    
    switch (type) {
      case 'disconnect':
        networkStatus.value = '已断开'
        addEvent('network', '网络连接断开')
        break
      case 'online':
        networkStatus.value = '已连接'
        addEvent('network', '网络已连接')
        break
      case 'reconnect':
        networkStatus.value = '已连接'
        addEvent('network', '重新连接成功')
        break
      case 'retry':
        networkStatus.value = '重连中'
        addEvent('network', `重连尝试 ${data.attempt + 1}`)
        break
    }
    
    lastNetworkUpdate.value = formatTime(new Date())
  }

  // Multi-device events
  const logoutHandler = (event) => {
    const { reason } = event.detail
    addEvent('conflict', `多端登录冲突: ${reason}`)
  }

  window.addEventListener('messaging-network-status', networkHandler)
  window.addEventListener('multi-device-logout', logoutHandler)

  eventListeners.push(
    () => window.removeEventListener('messaging-network-status', networkHandler),
    () => window.removeEventListener('multi-device-logout', logoutHandler)
  )
}

onMounted(() => {
  refreshStatus()
  setupEventListeners()
})

onUnmounted(() => {
  eventListeners.forEach(cleanup => cleanup())
})

// Handle overlay click to close modal
const handleOverlayClick = (event) => {
  if (event.target === event.currentTarget) {
    emit('close')
  }
}
</script>

<style scoped>
/* Modal styles - reusing existing modal system */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.developer-info-modal {
  background: var(--color-bg-primary);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-xl);
  border: var(--border-width) solid var(--color-border);
  width: 90%;
  max-width: 600px;
  max-height: 80vh;
  overflow-y: auto;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-3xl);
  padding-bottom: var(--spacing-xl);
  border-bottom: var(--border-width) solid var(--color-border);
}

.modal-header h3 {
  margin: 0;
  color: var(--color-text-primary);
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
}

.close-btn {
  background: none;
  border: none;
  color: var(--color-text-secondary);
  cursor: pointer;
  padding: var(--spacing-sm);
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.close-btn:hover {
  background-color: var(--color-bg-tertiary);
  color: var(--color-text-primary);
}

.modal-body {
  padding: var(--spacing-xl) var(--spacing-3xl);
  max-height: 60vh;
  overflow-y: auto;
}

.info-section {
  margin-bottom: var(--spacing-xl);
  padding-bottom: var(--spacing-lg);
  border-bottom: var(--border-width) solid var(--color-border);
}

.info-section:last-child {
  border-bottom: none;
  margin-bottom: 0;
}

.info-section h4 {
  margin: 0 0 var(--spacing-lg) 0;
  font-size: var(--font-size-md);
  color: var(--color-primary);
  font-weight: var(--font-weight-semibold);
}

.info-grid {
  display: grid;
  gap: var(--spacing-sm);
}

.info-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-sm) 0;
}

.label {
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
}

.value {
  color: var(--color-text-primary);
  font-weight: var(--font-weight-medium);
  font-size: var(--font-size-sm);
}

.status-connected { color: var(--color-success); }
.status-disconnected { color: var(--color-error); }
.status-reconnecting { color: var(--color-warning); }
.status-unknown { color: var(--color-text-secondary); }

.events-list {
  max-height: 200px;
  overflow-y: auto;
  background-color: var(--color-bg-secondary);
  border-radius: var(--radius-md);
  padding: var(--spacing-lg);
}

.event-item {
  display: grid;
  grid-template-columns: auto auto 1fr;
  gap: var(--spacing-sm);
  padding: var(--spacing-xs) 0;
  font-size: var(--font-size-xs);
  border-bottom: var(--border-width) solid var(--color-border-light);
}

.event-item:last-child {
  border-bottom: none;
}

.event-time {
  color: var(--color-text-secondary);
}

.event-type {
  font-weight: var(--font-weight-semibold);
  text-transform: uppercase;
}

.event-network { color: var(--color-primary); }
.event-conflict { color: var(--color-error); }
.event-refresh { color: var(--color-success); }
.event-export { color: var(--color-primary); }

.actions {
  display: flex;
  gap: var(--spacing-lg);
  flex-wrap: wrap;
}

.no-events {
  color: var(--color-text-secondary);
  font-style: italic;
  text-align: center;
  padding: var(--spacing-xl);
}
</style>
