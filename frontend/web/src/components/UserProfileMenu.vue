<template>
  <div class="user-profile-menu" ref="menuContainer">
    <button
      class="nickname-display"
      type="button"
      :aria-expanded="showMenu"
      aria-haspopup="true"
      :aria-label="`用户菜单：${authStore.user?.nickname || ''}`"
      @click="toggleMenu"
      @keydown="handleKeyDown">
      {{ authStore.user?.nickname || '' }}
    </button>

    <div
      v-if="showMenu"
      class="dropdown-menu"
      role="menu"
      :aria-labelledby="menuButtonId"
      @click.stop
      @keydown="handleMenuKeyDown">
      <button
        v-if="shouldShowNotificationButton"
        @click="handleNotificationToggle"
        class="menu-item"
        role="menuitem"
        type="button"
        :aria-describedby="notificationDescriptionId">
        启用通知
      </button>
      <button
        @click="handleEditProfile"
        class="menu-item"
        role="menuitem"
        type="button">
        编辑资料
      </button>
      <button
        @click="handleSettings"
        class="menu-item"
        role="menuitem"
        type="button">
        设置
      </button>
    </div>

    <!-- Screen reader description for notification button -->
    <div
      v-if="shouldShowNotificationButton"
      :id="notificationDescriptionId"
      class="sr-only">
      点击启用浏览器通知功能
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useAuthStore } from '../stores/auth'
import { notificationService } from '../services/notificationService'
import { uiLogger } from '../utils/logger.js'
import { handleError } from '../utils/errorHandler.js'

const emit = defineEmits(['edit-profile', 'settings'])

const authStore = useAuthStore()
const showMenu = ref(false)
const menuContainer = ref(null)

// Generate unique IDs for accessibility
const menuButtonId = `user-menu-button-${Math.random().toString(36).substr(2, 9)}`
const notificationDescriptionId = `notification-desc-${Math.random().toString(36).substr(2, 9)}`

// Notification settings reactive data
const notificationSettings = computed(() => notificationService.getNotificationSettings())

// Show notification button only when notifications are not enabled
const shouldShowNotificationButton = computed(() => {
  const settings = notificationSettings.value
  return settings.isSupported && !settings.canShow
})

// Menu state management
const toggleMenu = () => {
  showMenu.value = !showMenu.value
  uiLogger.debug('User menu toggled', { isOpen: showMenu.value })
}

const closeMenu = () => {
  showMenu.value = false
  uiLogger.debug('User menu closed')
}

// Menu item handlers
const handleEditProfile = () => {
  closeMenu()
  emit('edit-profile')
  uiLogger.debug('Edit profile action triggered')
}

const handleSettings = () => {
  closeMenu()
  emit('settings')
  uiLogger.debug('Settings action triggered')
}

const handleNotificationToggle = async () => {
  closeMenu()

  try {
    const settings = notificationSettings.value

    if (!settings.isSupported) {
      handleError(new Error('Browser does not support notifications'), {
        operation: 'enable_notifications',
        customMessage: '您的浏览器不支持通知功能',
        showToast: true,
      })
      return
    }

    if (settings.permission === 'denied') {
      handleError(new Error('Notification permission denied'), {
        operation: 'enable_notifications',
        customMessage: '通知权限已被拒绝，请在浏览器设置中手动开启通知权限',
        showToast: true,
      })
      return
    }

    // Request permission (this function only shows when permission is needed)
    const permission = await notificationService.requestPermission()
    if (permission === 'granted') {
      notificationService.setNotificationEnabled(true)
      uiLogger.info('Notifications enabled successfully')
    } else {
      uiLogger.warn('Notification permission denied by user')
    }
  } catch (error) {
    handleError(error, {
      operation: 'enable_notifications',
      context: 'UserProfileMenu',
      showToast: true,
    })
  }
}

// Keyboard navigation support
const handleKeyDown = (event) => {
  switch (event.key) {
    case 'Enter':
    case ' ': // Space key
      event.preventDefault()
      toggleMenu()
      break
    case 'Escape':
      if (showMenu.value) {
        event.preventDefault()
        closeMenu()
      }
      break
    case 'ArrowDown':
      if (!showMenu.value) {
        event.preventDefault()
        toggleMenu()
      }
      break
  }
}

const handleMenuKeyDown = (event) => {
  const menuItems = menuContainer.value?.querySelectorAll('.menu-item')
  if (!menuItems) return

  const currentIndex = Array.from(menuItems).findIndex(item => item === event.target)

  switch (event.key) {
    case 'Escape':
      event.preventDefault()
      closeMenu()
      // Focus back to menu button
      menuContainer.value?.querySelector('.nickname-display')?.focus()
      break
    case 'ArrowDown':
      event.preventDefault()
      const nextIndex = (currentIndex + 1) % menuItems.length
      menuItems[nextIndex]?.focus()
      break
    case 'ArrowUp':
      event.preventDefault()
      const prevIndex = currentIndex <= 0 ? menuItems.length - 1 : currentIndex - 1
      menuItems[prevIndex]?.focus()
      break
    case 'Home':
      event.preventDefault()
      menuItems[0]?.focus()
      break
    case 'End':
      event.preventDefault()
      menuItems[menuItems.length - 1]?.focus()
      break
  }
}



// Click outside handler
const handleClickOutside = (event) => {
  if (menuContainer.value && !menuContainer.value.contains(event.target)) {
    closeMenu()
  }
}

// Global escape key handler
const handleGlobalKeyDown = (event) => {
  if (event.key === 'Escape' && showMenu.value) {
    closeMenu()
  }
}

// Lifecycle hooks
onMounted(() => {
  document.addEventListener('click', handleClickOutside)
  document.addEventListener('keydown', handleGlobalKeyDown)
  uiLogger.debug('UserProfileMenu mounted')
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
  document.removeEventListener('keydown', handleGlobalKeyDown)
  uiLogger.debug('UserProfileMenu unmounted')
})
</script>

<style scoped>
.user-profile-menu {
  position: relative;
  display: inline-block;
}

.nickname-display {
  cursor: pointer;
  padding: var(--spacing-sm);
  border: none;
  background: none;
  border-radius: var(--border-radius-sm);
  transition: background-color 0.2s;
  color: var(--color-text-primary);
  user-select: none;
  font-size: inherit;
  font-family: inherit;
}

.nickname-display:hover {
  background-color: var(--color-bg-secondary);
}

.nickname-display:focus {
  outline: none;
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
  margin-top: var(--spacing-xs);
}

.menu-item {
  display: block;
  width: 100%;
  padding: var(--spacing-md) var(--spacing-lg);
  background: none;
  border: none;
  text-align: left;
  color: var(--color-text-primary);
  cursor: pointer;
  font-size: 0.9rem;
  font-family: inherit;
  transition: background-color 0.2s, box-shadow 0.2s;
}

.menu-item:hover,
.menu-item:focus {
  background-color: var(--color-bg-secondary);
  outline: none;
}

.menu-item:first-child {
  border-radius: var(--border-radius-sm) var(--border-radius-sm) 0 0;
}

.menu-item:last-child {
  border-radius: 0 0 var(--border-radius-sm) var(--border-radius-sm);
}



/* Screen reader only content */
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

.menu-item.notification-disabled {
  opacity: 0.6;
}

.menu-item.notification-disabled:hover {
  background-color: var(--color-bg-secondary);
  opacity: 0.8;
}
</style>
