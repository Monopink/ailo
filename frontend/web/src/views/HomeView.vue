<template>
  <!-- Desktop Layout -->
  <div v-if="!isMobile" class="home-container grid-bg">
    <div class="chat-container glass-panel">
      <!-- Chat sidebar -->
      <div class="chat-sidebar glass-panel">
        <ChatList />
      </div>

      <!-- Main chat area -->
      <div class="chat-main glass-panel">
        <ChatWindow />
      </div>
    </div>
  </div>

  <!-- Mobile Layout -->
  <div v-else class="mobile-container">
    <!-- Chat List View -->
    <div v-if="!selectedChatId" class="mobile-chat-list">
      <div class="mobile-header">
        <h1>会话</h1>
        <button class="logout-button" @click="handleLogout">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            <polyline points="16,17 21,12 16,7" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            <line x1="21" y1="12" x2="9" y2="12" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </button>
      </div>
      <ChatList />
    </div>

    <!-- Chat Window View -->
    <div v-else class="mobile-chat-window">
      <div class="mobile-chat-header">
        <button class="back-button" @click="goBackToList">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
            <path d="M15 18L9 12L15 6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </button>
        <h2>{{ selectedChat?.name || '聊天' }}</h2>
      </div>
      <ChatWindow />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue';
import ChatList from '../components/ChatList.vue';
import ChatWindow from '../components/ChatWindow.vue';
import { useChatStore } from '../stores/chat';
import { useAuthStore } from '../stores/auth';
import { useRouter } from 'vue-router';

const chatStore = useChatStore();
const authStore = useAuthStore();
const router = useRouter();

// Mobile detection
const isMobile = ref(false);

const checkMobile = () => {
  isMobile.value = window.innerWidth <= 767;
};

onMounted(() => {
  checkMobile();
  window.addEventListener('resize', checkMobile);
});

onUnmounted(() => {
  window.removeEventListener('resize', checkMobile);
});

// Mobile navigation
const selectedChatId = computed(() => chatStore.selectedChatId);
const selectedChat = computed(() => {
  return chatStore.chats.find(chat => chat.id === selectedChatId.value);
});

const goBackToList = () => {
  chatStore.selectChat(null);
};

const handleLogout = () => {
  authStore.logout();
  router.push('/login');
};
</script>

<style scoped>
/* Desktop Layout */
.home-container {
  position: fixed; /* 固定定位防止滚动 */
  top: 0;
  left: 0;
  width: 100%;
  height: 100vh;
  padding: 16px; /* Smaller padding */
  display: flex;
  justify-content: center;
  align-items: center;
  overflow: hidden;
}

.chat-container {
  display: flex;
  position: relative;
  height: var(--chat-container-height);
  width: var(--chat-container-width);
  max-width: var(--chat-container-max-width);
  background-color: var(--color-bg-overlay);
  overflow: hidden;
  border-radius: calc(var(--border-radius) + 10px); /* 外圆角 = 内圆角 + margin值 */
}

.chat-sidebar {
  flex: 0 0 280px;
  margin: 10px;
  border-radius: var(--border-radius);
  background-color: var(--color-bg-secondary);
  overflow: hidden;
}

.chat-main {
  flex-grow: 1;
  display: flex;
  flex-direction: column;
  margin: 10px;
  margin-left: 0;
  border-radius: var(--border-radius);
  overflow: hidden;
}

/* Mobile Layout */
.mobile-container {
  width: 100%;
  height: 100vh;
  background-color: var(--color-bg-primary);
  overflow: hidden; /* Prevent page scrolling */
}

.mobile-chat-list {
  width: 100%;
  height: 100vh;
  display: flex;
  flex-direction: column;
  overflow: hidden; /* Prevent page scrolling */
}

.mobile-header {
  background-color: var(--color-bg-secondary);
  border-bottom: var(--border-width) solid var(--color-border);
  padding: 1rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  position: sticky;
  top: 0;
  z-index: 10;
}

.mobile-header h1 {
  margin: 0;
  font-size: 1.2rem;
  font-weight: 500;
  color: var(--color-text-primary);
  flex: 1;
  text-align: center;
}

.logout-button {
  background: none;
  border: none;
  color: var(--color-text-primary);
  cursor: pointer;
  padding: 0.5rem;
  border-radius: var(--border-radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background-color 0.2s;
}

.logout-button:hover {
  background-color: var(--color-bg-tertiary);
}

.mobile-chat-window {
  width: 100%;
  height: 100vh;
  display: flex;
  flex-direction: column;
  overflow: hidden; /* Prevent page scrolling */
}

.mobile-chat-header {
  background-color: var(--color-bg-secondary);
  border-bottom: var(--border-width) solid var(--color-border);
  padding: 1rem;
  display: flex;
  align-items: center;
  gap: 1rem;
  position: sticky;
  top: 0;
  z-index: 10;
}

.back-button {
  background: none;
  border: none;
  color: var(--color-text-primary);
  cursor: pointer;
  padding: 0.5rem;
  border-radius: var(--border-radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background-color 0.2s;
}

.back-button:hover {
  background-color: var(--color-bg-tertiary);
}

.mobile-chat-header h2 {
  margin: 0;
  font-size: 1.1rem;
  font-weight: 500;
  color: var(--color-text-primary);
  flex: 1;
}
</style>