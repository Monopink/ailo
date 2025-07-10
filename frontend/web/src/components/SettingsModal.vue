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
const brandName = import.meta.env.VITE_BRAND_NAME || '敲敲'

// Notification settings
const notificationShowContent = ref(true)

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
  border-radius: var(--border-radius);
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.2);
  width: 90%;
  max-width: 500px;
  max-height: 80vh;
  overflow-y: auto;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.5rem;
  border-bottom: var(--border-width) solid var(--color-border);
}

.modal-header h3 {
  margin: 0;
  color: var(--color-text-primary);
  font-size: 1.25rem;
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
  padding: 1.5rem;
}

.settings-section {
  margin-bottom: 2rem;
}

.settings-section:last-child {
  margin-bottom: 0;
}

.settings-section h4 {
  margin: 0 0 1rem 0;
  color: var(--color-text-primary);
  font-size: 1rem;
  font-weight: 600;
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
  font-size: 0.95rem;
  line-height: 1.4;
}

.setting-description {
  margin: 0.5rem 0 0 2.25rem;
  color: var(--color-text-secondary);
  font-size: 0.85rem;
  line-height: 1.4;
}

.modal-footer {
  padding: 1rem 1.5rem;
  border-top: var(--border-width) solid var(--color-border);
  display: flex;
  justify-content: flex-end;
}

.btn {
  padding: 0.5rem 1rem;
  border: none;
  border-radius: var(--border-radius-sm);
  cursor: pointer;
  font-size: 0.9rem;
  transition: background-color 0.2s;
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
