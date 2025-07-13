<template>
  <div class="modal-overlay" @click="handleOverlayClick">
    <div class="modal-content" @click.stop>
      <div class="modal-header">
        <h3>设置</h3>
        <button @click="$emit('close')" class="close-button">×</button>
      </div>
      
      <div class="modal-body">
        <div class="settings-section">
          <h4>通知设置</h4>

          <!-- Notification content setting -->
          <div class="setting-item">
            <div class="setting-content">
              <div class="setting-info">
                <span class="setting-text">通知显示具体内容</span>
                <p class="setting-description">
                  关闭后，通知将只显示"你有一条{{ brandName }}新消息"，不显示具体消息内容
                </p>
              </div>
              <div class="setting-control">
                <input
                  type="checkbox"
                  v-model="notificationShowContent"
                  @change="handleNotificationContentToggle"
                  class="setting-checkbox"
                />
              </div>
            </div>
          </div>

          <!-- Notification status warning -->
          <div class="notification-status" v-if="notificationPermission === 'denied'">
            <p class="notification-warning">
              浏览器通知已禁用，请在网页设置中调整
            </p>
          </div>
        </div>

        <div class="settings-section">
          <h4>数据管理</h4>

          <div class="setting-item">
            <div class="setting-content">
              <div class="setting-info">
                <span class="setting-text">清除聊天记录</span>
                <p class="setting-description">
                  删除所有聊天记录，联系人列表将保留但聊天内容将被清空
                </p>
              </div>
              <div class="setting-control">
                <button @click="showClearConfirm = true" class="btn btn-danger">
                  清除
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Clear Chat Confirmation Dialog -->
    <div v-if="showClearConfirm" class="modal-overlay" @click="showClearConfirm = false">
      <div class="modal-content confirm-dialog" @click.stop>
        <div class="modal-header">
          <h3>确认清除聊天记录</h3>
        </div>

        <div class="modal-body">
          <p class="confirm-text">
            此操作将删除所有聊天记录，但保留联系人列表。此操作不可撤销，确定要继续吗？
          </p>
        </div>

        <div class="modal-footer">
          <button @click="showClearConfirm = false" class="btn btn-secondary">
            取消
          </button>
          <button @click="handleClearChatMessages" class="btn btn-danger" :disabled="isClearing">
            {{ isClearing ? '清除中...' : '确定清除' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { notificationService } from '../services/notificationService'
import { useChatStore } from '../stores/chat'
import { useToast } from 'vue-toastification'

const emit = defineEmits(['close'])
const chatStore = useChatStore()
const toast = useToast()

// Get brand name from environment variable
const brandName = import.meta.env.VITE_BRAND_NAME

// Notification settings
const notificationShowContent = ref(true)
const notificationPermission = ref(Notification.permission)

// Clear chat confirmation
const showClearConfirm = ref(false)
const isClearing = ref(false)



// Load current settings
onMounted(() => {
  const settings = notificationService.getNotificationSettings()
  notificationShowContent.value = settings.showContent !== false // Default to true
})

// Handle notification content toggle
const handleNotificationContentToggle = () => {
  notificationService.setNotificationShowContent(notificationShowContent.value)
  console.log('📢 Notification show content:', notificationShowContent.value)
}

// Handle clear chat messages
const handleClearChatMessages = async () => {
  if (isClearing.value) return

  isClearing.value = true

  try {
    const success = chatStore.clearAllChatMessages()

    if (success) {
      toast.success('聊天记录已清除')
      showClearConfirm.value = false
    } else {
      toast.error('清除聊天记录失败')
    }
  } catch (error) {
    console.error('Failed to clear chat messages:', error)
    toast.error('清除聊天记录时发生错误')
  } finally {
    isClearing.value = false
  }
}

// Handle overlay click to close modal
const handleOverlayClick = (event) => {
  if (event.target === event.currentTarget) {
    emit('close')
  }
}
</script>

<style scoped>
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

.modal-content {
  background: var(--color-bg-primary);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-xl);
  border: var(--border-width) solid var(--color-border);
  width: 90%;
  max-width: 480px;
  max-height: 80vh;
  overflow-y: auto;
}

/* Mobile optimizations */
@media (max-width: 767px) {
  .modal-content {
    width: 95%;
    max-height: 90vh;
    margin: var(--spacing-lg);
  }
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-3xl);
  padding-bottom: var(--spacing-xl);
}

.modal-header h3 {
  margin: 0;
  color: var(--color-text-primary);
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
}

.close-button {
  background: none;
  border: none;
  font-size: 1.5rem;
  color: var(--color-text-secondary);
  cursor: pointer;
  padding: 0;
  width: 30px;
  height: 30px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  transition: background-color 0.2s;
}

.close-button:hover {
  background-color: var(--color-bg-secondary);
}

.modal-body {
  padding: 0 var(--spacing-3xl) var(--spacing-xl);
}

.settings-section {
  margin-bottom: 2rem;
}

.settings-section:last-child {
  margin-bottom: 0;
}

.settings-section h4 {
  margin: 0 0 1rem 0;
  color: var(--color-text-secondary);
  font-size: var(--font-size-md);
  font-weight: var(--font-weight-normal);
}

.notification-status {
  margin-bottom: 1.5rem;
}

.notification-warning {
  margin: 0;
  padding: var(--spacing-lg) var(--spacing-xl);
  background-color: var(--color-warning-light);
  color: var(--color-text-primary);
  border-radius: var(--radius-lg);
  font-size: var(--font-size-sm);
  line-height: 1.4;
  border: var(--border-width) solid var(--color-warning);
}

.setting-item {
  margin-bottom: 1.5rem;
}

.setting-item:last-child {
  margin-bottom: 0;
}

.setting-content {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--spacing-xl);
}

.setting-info {
  flex: 1;
  text-align: left;
}

.setting-control {
  flex-shrink: 0;
  display: flex;
  align-items: flex-start;
  margin-top: 2px; /* Align with text baseline */
}

.setting-checkbox {
  margin: 0;
  width: 18px;
  height: 18px;
  cursor: pointer;
  flex-shrink: 0;
  accent-color: var(--color-primary);
  margin-top: 2px;
}

.setting-text {
  color: var(--color-text-primary);
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-medium);
  line-height: 1.4;
  display: block;
  margin-bottom: var(--spacing-sm);
}

.setting-description {
  margin: 0;
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
  line-height: 1.4;
}

.modal-footer {
  padding: var(--spacing-xl) var(--spacing-3xl);
  display: flex;
  justify-content: flex-end;
}

.btn {
  padding: var(--spacing-lg) var(--spacing-xl);
  border: none;
  border-radius: var(--radius-lg);
  cursor: pointer;
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-medium);
  transition: all 0.15s ease;
  height: var(--button-height-md);
}

.btn-primary {
  background-color: var(--color-primary);
  color: white;
  font-weight: 500;
}

.btn-primary:hover {
  background-color: var(--color-primary-hover);
  color: white;
}

.btn-secondary {
  background-color: var(--color-bg-secondary);
  color: var(--color-text-primary);
  border: var(--border-width) solid var(--color-border);
}

.btn-secondary:hover {
  background-color: var(--color-bg-tertiary);
}

.btn-danger {
  background-color: var(--color-error);
  color: white;
}

.btn-danger:hover {
  background-color: #dc2626; /* Darker red on hover */
}

.btn-danger:disabled {
  background-color: var(--color-bg-secondary);
  color: var(--color-text-secondary);
  cursor: not-allowed;
}

/* setting-action and setting-info styles are now replaced by setting-content and setting-info */

.confirm-dialog {
  max-width: 400px;
}

.confirm-text {
  margin: 0;
  color: var(--color-text-primary);
  font-size: var(--font-size-base);
  line-height: 1.5;
}

.modal-footer .btn + .btn {
  margin-left: var(--spacing-lg);
}
</style>
