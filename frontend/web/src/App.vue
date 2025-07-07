<template>
  <div id="main-layout">
    <header class="global-header hide-on-mobile" v-if="authStore.user">
      <div class="header-content">
        <div class="welcome-message">
          {{ authStore.user.nickname || authStore.user.username || authStore.user.phone }}
        </div>
        <div class="header-actions">
          <button @click="handleLogout" class="btn">登出</button>
        </div>
      </div>
    </header>

    <main :class="{ 'with-header': authStore.user }">
      <router-view />
    </main>

    <!-- Development test panel (development only) -->
    <DevTestPanel v-if="isDevelopment" />
  </div>
</template>

<script setup>
import { onMounted, watch, computed } from 'vue'
import { useAuthStore } from './stores/auth'
import { useChatStore } from './stores/chat'
import { useRouter } from 'vue-router'
import { messageService } from './services/messaging'
import DevTestPanel from './components/DevTestPanel.vue'


const authStore = useAuthStore()
const chatStore = useChatStore()
const router = useRouter()

// Development mode check
const isDevelopment = computed(() => import.meta.env.DEV)

const handleLogout = () => {
  authStore.logout()
  router.push('/login')
}

onMounted(async () => {
  console.log('App mounted - initializing...')

  // Version management is already initialized in main.js

  // LeanMessage initialization is now handled by messageService

  // Check authentication status
  await authStore.checkAuth()
})

// Watch for user login/logout
watch(() => authStore.user, async (newUser, oldUser) => {
  if (newUser && newUser.entity_id) {
    try {
      await messageService.initialize(String(newUser.entity_id))
      await chatStore.fetchBots()

      // Message handling is now done automatically by messageService
      // No need to set up manual listeners here
    } catch (error) {
      console.error('❌ Failed to connect to LeanMessage:', error)
    }
  } else if (oldUser) {
    try {
      console.log('User logged out, cleaning up message service...')
      await messageService.cleanup()
      chatStore.chats = []
      chatStore.selectedChatId = null
      console.log('✅ Message service cleaned up')
    } catch (error) {
      console.error('❌ Failed to cleanup message service:', error)
    }
  }
})
</script>

<style>
/* Global styles are now in assets/main.css */
#main-layout {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  border: none;
  background-color: var(--color-bg-primary);
}

.global-header {
  background-color: var(--color-bg-secondary);
  border-bottom: var(--border-width) solid var(--color-border);
  padding: 0 2rem;
  height: 50px;
  display: flex;
  align-items: center;
  position: sticky;
  top: 0;
  z-index: 10;
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
  height: 100%; /* 确保内容占满header高度 */
  max-width: var(--container-max-width);
  margin: 0 auto;
  padding: 0 1rem;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.welcome-message {
  font-size: 1rem;
  color: var(--color-text-primary);
}

main {
  flex: 1;
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 0;
  overflow: hidden; /* 防止页面滚动 */
  /* Remove padding to allow fullscreen apps */
}

main.with-header {
  height: calc(100vh - 50px);
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

  main.with-header {
    height: 100vh; /* Full height on mobile since header is hidden */
  }
}
</style>