<template>
  <div id="main-layout">
    <header class="global-header" v-if="authStore.user">
      <div class="header-content">
        <div class="welcome-message">
          {{ authStore.user.phone }}
        </div>
        <div class="header-actions">
          <button @click="handleLogout" class="btn">登出</button>
        </div>
      </div>
    </header>

    <main :class="{ 'with-header': authStore.user }">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { onMounted, watch } from 'vue'
import { useAuthStore } from './stores/auth'
import { useChatStore } from './stores/chat'
import { useRouter } from 'vue-router'
import { initLeanMessage, loginLeanMessage, logoutLeanMessage } from './services/leanmessage'
import { initVersionManagement } from './utils/version'

const authStore = useAuthStore()
const chatStore = useChatStore()
const router = useRouter()

const handleLogout = () => {
  authStore.logout()
  router.push('/login')
}

onMounted(async () => {
  console.log('App mounted - initializing...')

  // Initialize version management and cache control
  initVersionManagement()

  // Initialize LeanMessage
  try {
    await initLeanMessage()
    console.log('✅ LeanMessage initialized')
  } catch (error) {
    console.error('❌ Failed to initialize LeanMessage:', error)
  }

  // Check authentication status
  await authStore.checkAuth()
})

// Watch for user login/logout
watch(() => authStore.user, async (newUser, oldUser) => {
  if (newUser && newUser.entity_id) {
    try {
      console.log('User logged in, connecting to LeanMessage...')
      await loginLeanMessage(String(newUser.entity_id))
      await chatStore.fetchBots()
      console.log('✅ Connected to LeanMessage and fetched bots')
    } catch (error) {
      console.error('❌ Failed to connect to LeanMessage:', error)
    }
  } else if (oldUser) {
    try {
      console.log('User logged out, disconnecting from LeanMessage...')
      await logoutLeanMessage()
      chatStore.chats = []
      chatStore.selectedChatId = null
      console.log('✅ Disconnected from LeanMessage')
    } catch (error) {
      console.error('❌ Failed to disconnect from LeanMessage:', error)
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
  /* Remove padding to allow fullscreen apps */
}

main.with-header {
  height: calc(100vh - 50px);
}

/* Responsive adjustments */
@media (max-width: 767px) {
  .global-header {
    padding: 0 1rem;
    height: 44px;
  }

  .header-actions {
    gap: 0.5rem;
  }

  main.with-header {
    height: calc(100vh - 44px);
  }
}
</style>