<template>
  <div v-if="showStatus" class="dev-test-panel">
    <div class="panel-header">
      <h4>开发测试面板</h4>
      <button @click="toggleExpanded" class="toggle-btn">
        {{ expanded ? '收起' : '展开' }}
      </button>
    </div>

    <div v-if="expanded" class="panel-content">
      <!-- Environment Info -->
      <div class="test-section">
        <h5>环境信息</h5>
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
      <div class="test-section">
        <h5>多端登录</h5>
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
      <div class="test-section">
        <h5>网络状态</h5>
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
      <div class="test-section">
        <h5>消息服务</h5>
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
      <div class="test-section">
        <h5>测试事件</h5>
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
      <div class="test-section">
        <h5>测试操作</h5>
        <div class="actions">
          <button @click="refreshStatus" class="action-btn">刷新状态</button>
          <button @click="clearEvents" class="action-btn">清除事件</button>
          <button @click="testMessage" class="action-btn">测试消息</button>
          <button @click="exportStatus" class="action-btn">导出数据</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { multiDeviceManager } from '../services/messaging/multiDeviceManager'
import { multiDeviceConfig } from '../services/messaging/multiDeviceConfig'
import { messageService } from '../services/messaging/messageService'
import { useAuthStore } from '../stores/auth'
import { LoginStrategy, ConflictAction, DeviceTypeLabels, LoginStrategyLabels } from '../services/messaging/types'

export default {
  name: 'DevTestPanel',
  setup() {
    const authStore = useAuthStore()

    // Only show in development environment and on desktop/web (not mobile)
    const showStatus = computed(() => {
      if (!import.meta.env.DEV) return false

      // Hide on mobile devices
      const userAgent = navigator.userAgent.toLowerCase()
      const isMobile = /android|iphone|ipod|blackberry|iemobile|opera mini/i.test(userAgent)
      const isTablet = /ipad|android(?!.*mobile)/i.test(userAgent)

      return !isMobile && !isTablet
    })
    const expanded = ref(false)
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

    const toggleExpanded = () => {
      expanded.value = !expanded.value
    }

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
        case LoginStrategy.UNLIMITED:
          return '无限制多端'
        case LoginStrategy.SINGLE_DEVICE:
          return '单设备'
        case LoginStrategy.LIMITED_MULTI:
          return '限制多端'
        default:
          return '未知'
      }
    }

    const getConflictActionLabel = (action) => {
      switch (action) {
        case ConflictAction.FORCE_LOGOUT:
          return '强制下线'
        case ConflictAction.REJECT_NEW:
          return '拒绝新登录'
        case ConflictAction.NOTIFY_ONLY:
          return '仅通知'
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
        const { reason, conflictInfo } = event.detail
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

    return {
      showStatus,
      expanded,
      deviceInfo,
      networkStatus,
      messageServiceStatus,
      lastNetworkUpdate,
      recentEvents,
      isDev,
      appVersion,
      currentUserId,
      toggleExpanded,
      refreshStatus,
      clearEvents,
      testMessage,
      exportStatus,
      getDeviceTypeLabel,
      getStrategyLabel,
      getConflictActionLabel,
      networkStatusClass,
      messageServiceStatusClass,
      formatTime
    }
  }
}
</script>

<style scoped>
.dev-test-panel {
  position: fixed;
  top: 70px; /* Avoid overlap with header */
  right: 10px;
  background: rgba(0, 0, 0, 0.95);
  color: white;
  border-radius: 8px;
  padding: 12px;
  font-size: 12px;
  max-width: 450px;
  max-height: calc(100vh - 80px); /* Account for header height */
  overflow-y: auto;
  z-index: 9999;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  border: 2px solid #07c160;
}

/* Hide on mobile devices */
@media (max-width: 768px) {
  .dev-test-panel {
    display: none;
  }
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  padding-bottom: 8px;
  border-bottom: 1px solid #333;
}

.panel-header h4 {
  margin: 0;
  font-size: 14px;
  color: #07c160;
}

.toggle-btn {
  background: #07c160;
  color: white;
  border: none;
  border-radius: 4px;
  padding: 4px 8px;
  font-size: 10px;
  cursor: pointer;
}

.test-section {
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid #333;
}

.test-section h5 {
  margin: 0 0 6px 0;
  font-size: 12px;
  color: #17a2b8;
  font-weight: bold;
}

.info-grid {
  display: grid;
  gap: 4px;
}

.info-item {
  display: flex;
  justify-content: space-between;
}

.label {
  color: #aaa;
}

.value {
  color: white;
  font-weight: bold;
}

.status-connected { color: #28a745; }
.status-disconnected { color: #dc3545; }
.status-reconnecting { color: #ffc107; }
.status-unknown { color: #6c757d; }

.events-list {
  max-height: 120px;
  overflow-y: auto;
}

.event-item {
  display: grid;
  grid-template-columns: auto auto 1fr;
  gap: 8px;
  padding: 2px 0;
  font-size: 10px;
}

.event-time {
  color: #888;
}

.event-type {
  font-weight: bold;
  text-transform: uppercase;
}

.event-network { color: #17a2b8; }
.event-conflict { color: #dc3545; }
.event-refresh { color: #28a745; }
.event-export { color: #6f42c1; }

.actions {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.action-btn {
  background: #6c757d;
  color: white;
  border: none;
  border-radius: 4px;
  padding: 4px 8px;
  font-size: 10px;
  cursor: pointer;
}

.action-btn:hover {
  background: #5a6268;
}

.no-events {
  color: #888;
  font-style: italic;
  text-align: center;
  padding: 8px;
}
</style>
