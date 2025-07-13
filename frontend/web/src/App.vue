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


  </div>
</template>

<script setup>
import { onMounted, watch, ref } from 'vue'
import { useAuthStore } from './stores/auth'
import ProfileSetupModal from './components/ProfileSetupModal.vue'
import ProfileEditModal from './components/ProfileEditModal.vue'
import SettingsModal from './components/SettingsModal.vue'
import { useChatStore } from './stores/chat'
import { useRouter } from 'vue-router'
import { messageService } from './services/messaging'
import { messageStatusManager } from './services/messaging/messageStatusManager'
import { notificationService } from './services/notificationService'
const authStore = useAuthStore()
const chatStore = useChatStore()
const router = useRouter()

// Modal states
const showEditModal = ref(false)
const showSettingsModal = ref(false)

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
      console.log('🔄 User logged in, initializing services...', newUser.id)

      // Initialize chat store with user context
      await chatStore.initializeWithUser(newUser.id)

      // Initialize message status manager with user context
      await messageStatusManager.initialize(newUser.id)

      // Initialize message service
      await messageService.initialize(newUser.id)

      // Fetch contacts after all services are initialized
      await chatStore.fetchContacts()

      // Start periodic refresh of contacts
      chatStore.startPeriodicRefresh()

      // Request notification permission on first login (if not asked before)
      await requestNotificationPermissionIfNeeded()

      console.log('✅ All services initialized for user', newUser.id)
    } catch (error) {
      console.error('❌ Failed to initialize services for user:', error)
    }
  } else if (oldUser) {
    try {
      console.log('🔄 User logged out, cleaning up services...', oldUser.id)

      // Stop periodic refresh
      chatStore.stopPeriodicRefresh()

      // Cleanup message service
      await messageService.cleanup()

      // Cleanup message status manager (saves state before clearing)
      await messageStatusManager.cleanup()

      // Clear chat store user context (preserves localStorage data)
      chatStore.clearUserContext()

      console.log('✅ All services cleaned up for user', oldUser.id)
    } catch (error) {
      console.error('❌ Failed to cleanup services:', error)
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