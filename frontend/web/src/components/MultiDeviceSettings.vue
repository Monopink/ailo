<template>
  <div class="multi-device-settings">
    <h3>多端登录设置</h3>
    
    <!-- Login Strategy -->
    <div class="setting-group">
      <label class="setting-label">登录策略</label>
      <select v-model="localConfig.loginStrategy" @change="updateConfig" class="setting-select">
        <option :value="LoginStrategy.UNLIMITED">无限制多端登录</option>
        <option :value="LoginStrategy.LIMITED_MULTI">限制多端登录（推荐）</option>
        <option :value="LoginStrategy.SINGLE_DEVICE">单设备登录</option>
      </select>
      <p class="setting-description">
        {{ getStrategyDescription(localConfig.loginStrategy) }}
      </p>
    </div>

    <!-- Conflict Action -->
    <div class="setting-group">
      <label class="setting-label">冲突处理方式</label>
      <select v-model="localConfig.conflictAction" @change="updateConfig" class="setting-select">
        <option :value="ConflictAction.FORCE_LOGOUT">强制下线旧设备</option>
        <option :value="ConflictAction.REJECT_NEW">拒绝新设备登录</option>
        <option :value="ConflictAction.NOTIFY_ONLY">仅通知不处理</option>
      </select>
      <p class="setting-description">
        {{ getConflictDescription(localConfig.conflictAction) }}
      </p>
    </div>

    <!-- Auto Reconnect -->
    <div class="setting-group">
      <label class="setting-label">
        <input 
          type="checkbox" 
          v-model="localConfig.autoReconnect.enabled" 
          @change="updateConfig"
        />
        启用自动重连
      </label>
      <div v-if="localConfig.autoReconnect.enabled" class="sub-settings">
        <div class="setting-row">
          <label>最大重试次数:</label>
          <input 
            type="number" 
            v-model.number="localConfig.autoReconnect.maxAttempts" 
            @change="updateConfig"
            min="0" 
            max="10"
            class="setting-input"
          />
        </div>
        <div class="setting-row">
          <label>基础延迟 (毫秒):</label>
          <input 
            type="number" 
            v-model.number="localConfig.autoReconnect.baseDelay" 
            @change="updateConfig"
            min="100" 
            max="10000"
            step="100"
            class="setting-input"
          />
        </div>
      </div>
    </div>

    <!-- Notifications -->
    <div class="setting-group">
      <label class="setting-label">通知设置</label>
      <div class="checkbox-group">
        <label>
          <input 
            type="checkbox" 
            v-model="localConfig.notifications.showConflictNotifications" 
            @change="updateConfig"
          />
          显示登录冲突通知
        </label>
        <label>
          <input 
            type="checkbox" 
            v-model="localConfig.notifications.showReconnectNotifications" 
            @change="updateConfig"
          />
          显示重连通知
        </label>
        <label>
          <input 
            type="checkbox" 
            v-model="localConfig.notifications.showDeviceChangeNotifications" 
            @change="updateConfig"
          />
          显示设备变更通知
        </label>
      </div>
    </div>

    <!-- Development Settings (only in dev mode) -->
    <div v-if="isDevelopment" class="setting-group dev-settings">
      <label class="setting-label">开发设置</label>
      <div class="checkbox-group">
        <label>
          <input 
            type="checkbox" 
            v-model="localConfig.development.enableDebugLogs" 
            @change="updateConfig"
          />
          启用调试日志
        </label>
        <label>
          <input 
            type="checkbox" 
            v-model="localConfig.development.simulateConflicts" 
            @change="updateConfig"
          />
          模拟登录冲突
        </label>
      </div>
      <div class="setting-row">
        <label>模拟设备类型:</label>
        <select v-model="localConfig.development.mockDeviceType" @change="updateConfig" class="setting-select">
          <option :value="null">自动检测</option>
          <option :value="DeviceType.WEB">Web</option>
          <option :value="DeviceType.MOBILE">Mobile</option>
          <option :value="DeviceType.PAD">Pad</option>
          <option :value="DeviceType.DESKTOP">Desktop</option>
        </select>
      </div>
    </div>

    <!-- Actions -->
    <div class="setting-actions">
      <button @click="resetToDefaults" class="action-btn reset-btn">
        重置为默认设置
      </button>
      <button @click="exportConfig" class="action-btn export-btn">
        导出配置
      </button>
      <button @click="importConfig" class="action-btn import-btn">
        导入配置
      </button>
    </div>

    <!-- Hidden file input for import -->
    <input 
      ref="fileInput" 
      type="file" 
      accept=".json" 
      @change="handleFileImport" 
      style="display: none"
    />
  </div>
</template>

<script>
import { ref, reactive, computed, onMounted } from 'vue'
import { multiDeviceConfig } from '../services/messaging/multiDeviceConfig'
import { LoginStrategy, ConflictAction, DeviceType } from '../services/messaging/types'

export default {
  name: 'MultiDeviceSettings',
  setup() {
    const localConfig = reactive({})
    const fileInput = ref(null)
    
    const isDevelopment = computed(() => import.meta.env.DEV)

    const loadConfig = () => {
      Object.assign(localConfig, multiDeviceConfig.getConfig())
    }

    const updateConfig = () => {
      multiDeviceConfig.updateConfig(localConfig)
    }

    const resetToDefaults = () => {
      if (confirm('确定要重置为默认设置吗？这将清除所有自定义配置。')) {
        multiDeviceConfig.resetToDefaults()
        loadConfig()
      }
    }

    const exportConfig = () => {
      const config = multiDeviceConfig.getConfig()
      const blob = new Blob([JSON.stringify(config, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `multi-device-config-${Date.now()}.json`
      a.click()
      URL.revokeObjectURL(url)
    }

    const importConfig = () => {
      fileInput.value?.click()
    }

    const handleFileImport = (event) => {
      const file = event.target.files[0]
      if (!file) return

      const reader = new FileReader()
      reader.onload = (e) => {
        try {
          const importedConfig = JSON.parse(e.target.result)
          multiDeviceConfig.updateConfig(importedConfig)
          loadConfig()
          alert('配置导入成功！')
        } catch (error) {
          alert('配置文件格式错误，导入失败。')
          console.error('Config import error:', error)
        }
      }
      reader.readAsText(file)
    }

    const getStrategyDescription = (strategy) => {
      switch (strategy) {
        case LoginStrategy.UNLIMITED:
          return '允许用户在任意数量的设备上同时登录，所有设备都能接收消息。'
        case LoginStrategy.LIMITED_MULTI:
          return '允许用户在不同类型的设备上登录（如手机、平板、电脑），但同类型设备只能有一个在线。'
        case LoginStrategy.SINGLE_DEVICE:
          return '只允许用户在一个设备上登录，新设备登录会强制旧设备下线。'
        default:
          return ''
      }
    }

    const getConflictDescription = (action) => {
      switch (action) {
        case ConflictAction.FORCE_LOGOUT:
          return '当检测到登录冲突时，强制让较早登录的设备下线。'
        case ConflictAction.REJECT_NEW:
          return '当检测到登录冲突时，拒绝新设备的登录请求。'
        case ConflictAction.NOTIFY_ONLY:
          return '当检测到登录冲突时，仅显示通知，不进行任何强制操作。'
        default:
          return ''
      }
    }

    onMounted(() => {
      loadConfig()
    })

    return {
      localConfig,
      fileInput,
      isDevelopment,
      LoginStrategy,
      ConflictAction,
      DeviceType,
      updateConfig,
      resetToDefaults,
      exportConfig,
      importConfig,
      handleFileImport,
      getStrategyDescription,
      getConflictDescription
    }
  }
}
</script>

<style scoped>
.multi-device-settings {
  max-width: 600px;
  margin: 0 auto;
  padding: 20px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.multi-device-settings h3 {
  margin-top: 0;
  color: #333;
  border-bottom: 2px solid #07c160;
  padding-bottom: 10px;
}

.setting-group {
  margin-bottom: 24px;
  padding: 16px;
  border: 1px solid #e9ecef;
  border-radius: 6px;
}

.setting-label {
  display: block;
  font-weight: bold;
  margin-bottom: 8px;
  color: #495057;
}

.setting-select,
.setting-input {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #ced4da;
  border-radius: 4px;
  font-size: 14px;
}

.setting-description {
  margin-top: 8px;
  font-size: 12px;
  color: #6c757d;
  line-height: 1.4;
}

.sub-settings {
  margin-top: 12px;
  padding-left: 20px;
  border-left: 3px solid #e9ecef;
}

.setting-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.setting-row label {
  margin-right: 12px;
  font-weight: normal;
}

.setting-row .setting-input {
  width: 120px;
}

.checkbox-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.checkbox-group label {
  display: flex;
  align-items: center;
  font-weight: normal;
}

.checkbox-group input[type="checkbox"] {
  margin-right: 8px;
}

.dev-settings {
  background: #f8f9fa;
  border-color: #ffc107;
}

.dev-settings .setting-label {
  color: #856404;
}

.setting-actions {
  display: flex;
  gap: 12px;
  justify-content: center;
  margin-top: 24px;
  padding-top: 20px;
  border-top: 1px solid #e9ecef;
}

.action-btn {
  padding: 10px 20px;
  border: none;
  border-radius: 4px;
  font-size: 14px;
  cursor: pointer;
  transition: background-color 0.2s;
}

.reset-btn {
  background: #dc3545;
  color: white;
}

.reset-btn:hover {
  background: #c82333;
}

.export-btn {
  background: #28a745;
  color: white;
}

.export-btn:hover {
  background: #218838;
}

.import-btn {
  background: #07c160;
  color: white;
  font-weight: 500;
}

.import-btn:hover {
  background: #06ad56;
}
</style>
