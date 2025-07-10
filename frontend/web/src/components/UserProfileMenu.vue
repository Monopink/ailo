<template>
  <div class="user-profile-menu" ref="menuContainer">
    <div class="nickname-display" @click="toggleMenu">
      {{ authStore.user?.nickname || '点击设置昵称' }}
    </div>
    
    <div v-if="showMenu" class="dropdown-menu" @click.stop>
      <button @click="handleEditProfile" class="menu-item">
        编辑资料
      </button>
      <button @click="handleSettings" class="menu-item">
        设置
      </button>
      <button
        v-if="shouldShowNotificationButton"
        @click="handleNotificationToggle"
        class="menu-item">
        启用通知
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useAuthStore } from '../stores/auth'
import { notificationService } from '../services/notificationService'

const emit = defineEmits(['edit-profile', 'settings'])

const authStore = useAuthStore()
const showMenu = ref(false)
const menuContainer = ref(null)

// Notification settings reactive data
const notificationSettings = computed(() => notificationService.getNotificationSettings())

// Show notification button only when notifications are not enabled
const shouldShowNotificationButton = computed(() => {
  const settings = notificationSettings.value
  return settings.isSupported && !settings.canShow
})

const toggleMenu = () => {
  showMenu.value = !showMenu.value
}

const handleEditProfile = () => {
  showMenu.value = false
  emit('edit-profile')
}

const handleSettings = () => {
  showMenu.value = false
  emit('settings')
}

const handleNotificationToggle = async () => {
  showMenu.value = false

  const settings = notificationSettings.value

  if (!settings.isSupported) {
    alert('您的浏览器不支持通知功能')
    return
  }

  if (settings.permission === 'denied') {
    alert('通知权限已被拒绝，请在浏览器设置中手动开启通知权限')
    return
  }

  // Request permission (this function only shows when permission is needed)
  const permission = await notificationService.requestPermission()
  if (permission === 'granted') {
    notificationService.setNotificationEnabled(true)
    console.log('📢 Notifications enabled')
  } else {
    console.log('📢 Notification permission denied')
  }
}



const handleClickOutside = (event) => {
  if (menuContainer.value && !menuContainer.value.contains(event.target)) {
    showMenu.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})
</script>

<style scoped>
.user-profile-menu {
  position: relative;
  display: inline-block;
}

.nickname-display {
  cursor: pointer;
  padding: 0.5rem;
  border-radius: var(--border-radius-sm);
  transition: background-color 0.2s;
  color: var(--color-text-primary);
  user-select: none;
}

.nickname-display:hover {
  background-color: var(--color-bg-secondary);
}

.dropdown-menu {
  position: absolute;
  top: 100%;
  left: 0;
  background: var(--color-bg-primary);
  border: var(--border-width) solid var(--color-border);
  border-radius: var(--border-radius-sm);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  min-width: 120px;
  z-index: 1000;
  margin-top: 0.25rem;
}

.menu-item {
  display: block;
  width: 100%;
  padding: 0.75rem 1rem;
  background: none;
  border: none;
  text-align: left;
  color: var(--color-text-primary);
  cursor: pointer;
  font-size: 0.9rem;
  transition: background-color 0.2s;
}

.menu-item:hover {
  background-color: var(--color-bg-secondary);
}

.menu-item:first-child {
  border-radius: var(--border-radius-sm) var(--border-radius-sm) 0 0;
}

.menu-item:last-child {
  border-radius: 0 0 var(--border-radius-sm) var(--border-radius-sm);
}



.menu-item.notification-disabled {
  opacity: 0.6;
}

.menu-item.notification-disabled:hover {
  background-color: var(--color-bg-secondary);
  opacity: 0.8;
}
</style>
