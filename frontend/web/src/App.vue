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
import { messageService } from './services/messaging'
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

  // LeanMessage initialization is now handled by messageService

  // Check authentication status
  await authStore.checkAuth()
})

// Watch for user login/logout
watch(() => authStore.user, async (newUser, oldUser) => {
  if (newUser && newUser.entity_id) {
    try {
      console.log('User logged in, initializing message service...')
      await messageService.initialize(String(newUser.entity_id))

      await chatStore.fetchBots()
      console.log('✅ Message service initialized and fetched bots')
      console.log('Chat store chats:', chatStore.chats.length)

      // Setup message listener using new message service
      console.log('Setting up message listener...')
      messageService.onMessage((message, _conversation) => {
        console.log('📨 Received message:', message)

        // Handle different message types
        if (message.type === 1) { // CHAT message
          // Find the chat by sender - compatible with both bot and user messages
          const senderEntityId = message.from
          const chat = chatStore.chats.find(c => c.entity_id === senderEntityId || c.id === senderEntityId)

          if (chat) {
            const newMessage = {
              id: Date.now(), // Generate a simple ID
              text: message.content, // Use 'text' field to match MessageBubble component
              sender: message.from === String(newUser.entity_id) ? 'user' : 'bot',
              timestamp: new Date(message.timestamp),
              isFromUser: message.from === String(newUser.entity_id)
            }

            chatStore.addMessage(chat.id, newMessage)

            // Hide typing indicator when receiving a chat message
            // Use chat.id (which might be conversation_id) for event
            window.dispatchEvent(new CustomEvent('chat-message-received', {
              detail: { message, chatId: chat.id }
            }))
          } else {
            console.warn('📨 No chat found for message from:', senderEntityId)
          }
        }
        // Note: typing messages (type 2, 3) will be handled by ChatWindow component
      })

      // Setup typing message listener
      messageService.onTyping((message, _conversation) => {
        console.log('📨 Received typing message:', message)
        // Typing messages will be handled by individual ChatWindow components
        // We'll emit a global event that ChatWindow can listen to
        window.dispatchEvent(new CustomEvent('typing-message', {
          detail: { message, conversation: _conversation }
        }))
      })

      console.log('✅ Message listener setup complete')
    } catch (error) {
      console.error('❌ Failed to connect to LeanMessage:', error)
      console.error('Error details:', error.message, error.stack)
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