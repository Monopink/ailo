<template>
  <!-- Desktop Layout -->
  <div v-if="!isMobile" class="home-container">
    <div class="chat-app glass-panel">
      <!-- Chat sidebar -->
      <div class="chat-sidebar">
        <ChatList @edit-profile="handleEditProfile" @settings="handleSettings" />
      </div>

      <!-- Main chat area -->
      <div class="chat-main">
        <ChatWindow />
      </div>
    </div>
  </div>

  <!-- Mobile Layout -->
  <div v-else class="mobile-container">
    <!-- Chat List View -->
    <div v-if="!selectedChatId" class="mobile-chat-list">
      <div class="mobile-header">
        <h1>{{ APP_CONFIG.BRAND_NAME }}</h1>
      </div>
      <ChatList @edit-profile="handleEditProfile" @settings="handleSettings" />
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

  <!-- Profile Edit Modal -->
  <ProfileEditModal
    v-if="showEditModal"
    @close="showEditModal = false"
    @success="handleProfileEditSuccess"
  />

  <!-- Settings Modal -->
  <SettingsModal
    v-if="showSettingsModal"
    @close="handleSettingsClose"
  />


</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue';
import ChatList from '../components/ChatList.vue';
import ChatWindow from '../components/ChatWindow.vue';
import ProfileEditModal from '../components/ProfileEditModal.vue';
import SettingsModal from '../components/SettingsModal.vue';

import { useChatStore } from '../stores/chat';
import { useAuthStore } from '../stores/auth';
import { useRouter } from 'vue-router';
import { APP_CONFIG } from '../config/constants';

const chatStore = useChatStore();
const authStore = useAuthStore();
const router = useRouter();

// Modal states
const showEditModal = ref(false);
const showSettingsModal = ref(false);

// Mobile detection
const isMobile = ref(false);

const checkMobile = () => {
  isMobile.value = window.innerWidth <= 767;
};

onMounted(async () => {
  checkMobile();
  window.addEventListener('resize', checkMobile);

  // Set global chat store reference for message service
  window.__CHAT_STORE__ = chatStore;

  // 如果聊天列表为空且用户已登录，尝试重新获取联系人
  if (authStore.user && chatStore.chats.length === 0 && !chatStore.isLoaded) {
    try {
      await chatStore.fetchContacts();
    } catch (error) {
      console.error('Failed to fetch contacts on mount:', error);
    }
  }
});

onUnmounted(() => {
  window.removeEventListener('resize', checkMobile);

  // Clean up global reference
  if (window.__CHAT_STORE__) {
    delete window.__CHAT_STORE__;
  }
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

const handleEditProfile = () => {
  showEditModal.value = true;
};

const handleSettings = () => {
  showSettingsModal.value = true;
};

const handleProfileEditSuccess = () => {
  // Profile updated successfully
};

const handleSettingsClose = () => {
  showSettingsModal.value = false;
};
</script>

<style scoped>
/* Desktop Layout - Unified App */
.home-container {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100vh;
  padding: var(--spacing-xl);
  display: flex;
  justify-content: center;
  align-items: center;
  overflow: hidden;
  background: var(--color-bg-app);
}

.chat-app {
  display: flex;
  height: var(--chat-container-height);
  width: var(--chat-container-width);
  max-width: var(--chat-container-max-width);
  overflow: hidden;
  border: var(--border-width) solid var(--color-border-subtle);
}

.chat-sidebar {
  flex: 0 0 280px;
  background-color: var(--color-bg-secondary);
  border-right: var(--border-width) solid var(--color-border);
  overflow: hidden;
}

.chat-main {
  flex-grow: 1;
  display: flex;
  flex-direction: column;
  background-color: var(--color-bg-primary);
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
  padding: var(--spacing-xl);
  display: flex;
  align-items: center;
  justify-content: center;
  position: sticky;
  top: 0;
  z-index: 10;
}

.mobile-header h1 {
  margin: 0;
  font-size: var(--font-size-xl);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
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
  padding: var(--spacing-lg);
  display: flex;
  align-items: center;
  gap: var(--spacing-lg);
  position: sticky;
  top: 0;
  z-index: 10;
}

.back-button {
  background: none;
  border: none;
  color: var(--color-text-primary);
  cursor: pointer;
  padding: var(--spacing-sm);
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