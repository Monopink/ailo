<template>
  <div id="main-layout">
    <main>
      <router-view />
    </main>

    <!-- Profile Setup Modal -->
    <ProfileSetupModal
      v-if="authStore.needsProfileSetup && authStore.user"
      @close="handleProfileSetupClose"
      @success="handleProfileSetupSuccess"
    />

    <!-- Profile Edit Modal -->
    <ProfileEditModal
      v-if="showEditModal"
      @close="showEditModal = false"
      @success="handleProfileEditSuccess"
    />

    <!-- Settings Modal -->
    <SettingsModal
      v-if="showSettingsModal"
      @close="showSettingsModal = false"
    />

    <!-- Development test panel (development only) -->
    <DevTestPanel v-if="isDevelopment" />
  </div>
</template>

<script setup>
import { onMounted, watch, computed, ref } from 'vue'
import { useAuthStore } from './stores/auth'
import ProfileSetupModal from './components/ProfileSetupModal.vue'
import ProfileEditModal from './components/ProfileEditModal.vue'
import SettingsModal from './components/SettingsModal.vue'
import { useChatStore } from './stores/chat'
import { useRouter } from 'vue-router'
import { messageService } from './services/messaging'
import { notificationService } from './services/notificationService'
import DevTestPanel from './components/DevTestPanel.vue'

const authStore = useAuthStore()
const chatStore = useChatStore()
const router = useRouter()

// Development mode check
const isDevelopment = computed(() => import.meta.env.DEV)

// Modal states
const showEditModal = ref(false)
const showSettingsModal = ref(false)

const handleEditProfile = () => {
  showEditModal.value = true
}

const handleSettings = () => {
  showSettingsModal.value = true
}

const handleProfileSetupClose = () => {
  // Profile setup is required, so we don't allow closing without completion
  // This function is kept for consistency but doesn't do anything
}

const handleProfileSetupSuccess = () => {
  // Profile setup completed successfully
}

const handleProfileEditSuccess = () => {
  // Profile updated successfully
}

onMounted(async () => {
  // Version management is already initialized in main.js

  // LeanMessage initialization is now handled by messageService

  // Check authentication status
  await authStore.checkAuth()
})

// Watch for user login/logout
watch(() => authStore.user, async (newUser, oldUser) => {
  if (newUser && newUser.id) {
    try {
      await messageService.initialize(newUser.id)
      await chatStore.fetchContacts()

      // Start periodic refresh of contacts
      chatStore.startPeriodicRefresh()

      // Request notification permission on first login (if not asked before)
      await requestNotificationPermissionIfNeeded()

      // Message handling is now done automatically by messageService
      // No need to set up manual listeners here
    } catch (error) {
      console.error('❌ Failed to connect to LeanMessage:', error)
    }
  } else if (oldUser) {
    try {
      console.log('User logged out, cleaning up message service...')

      // Stop periodic refresh
      chatStore.stopPeriodicRefresh()

      await messageService.cleanup()
      chatStore.chats = []
      chatStore.selectedChatId = null
      console.log('✅ Message service cleaned up')
    } catch (error) {
      console.error('❌ Failed to cleanup message service:', error)
    }
  }
})

// Request notification permission on first login
const requestNotificationPermissionIfNeeded = async () => {
  const settings = notificationService.getNotificationSettings()

  // Only request if supported, not asked before, and permission is default
  if (settings.isSupported &&
      !settings.hasAskedBefore &&
      settings.permission === 'default') {

    console.log('📢 Requesting notification permission on first login')
    const permission = await notificationService.requestPermission()

    if (permission === 'granted') {
      notificationService.setNotificationEnabled(true)
      console.log('📢 Notifications enabled on first login')
    } else {
      console.log('📢 Notification permission denied on first login')
    }
  }
}
</script>

<style>
/* Modern App Layout */
#main-layout {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  background-color: var(--color-bg-primary);
}

main {
  flex: 1;
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 0;
  overflow: hidden;
  height: 100vh;
}

/* Hide on mobile utility class */
.hide-on-mobile {
  display: block;
}

/* Responsive adjustments */
@media (max-width: 767px) {
  .hide-on-mobile {
    display: none !important;
  }
}
</style>