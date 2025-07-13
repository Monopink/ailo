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

          <!-- Notification content setting - always visible -->
          <div class="setting-item">
            <label class="setting-label">
              <input
                type="checkbox"
                v-model="notificationShowContent"
                @change="handleNotificationContentToggle"
                class="setting-checkbox"
              />
              <span class="setting-text">通知显示具体内容</span>
            </label>
            <p class="setting-description">
              关闭后，通知将只显示"你有一条{{ brandName }}新消息"，不显示具体消息内容
            </p>
          </div>

          <!-- Notification status warning -->
          <div class="notification-status" v-if="notificationPermission === 'denied'">
            <p class="notification-warning">
              浏览器通知已禁用，请在网页设置中调整
            </p>
          </div>
        </div>
      </div>
      
      <div class="modal-footer">
        <button @click="$emit('close')" class="btn btn-primary">确定</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { notificationService } from '../services/notificationService'

const emit = defineEmits(['close'])

// Get brand name from environment variable
const brandName = import.meta.env.VITE_BRAND_NAME

// Notification settings
const notificationShowContent = ref(true)
const notificationPermission = ref(Notification.permission)



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

.setting-label {
  display: flex;
  align-items: flex-start;
  cursor: pointer;
  gap: 0.75rem;
}

.setting-checkbox {
  margin: 0;
  width: 18px;
  height: 18px;
  cursor: pointer;
  flex-shrink: 0;
  margin-top: 2px;
}

.setting-text {
  color: var(--color-text-primary);
  font-size: var(--font-size-base);
  line-height: 1.4;
}

.setting-description {
  margin: 0.5rem 0 0 2.25rem;
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
</style>
