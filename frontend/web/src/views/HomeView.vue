<template>
  <!-- Desktop Layout -->
  <div v-if="!isMobile" class="home-container">
    <div class="chat-app glass-panel">
      <!-- Chat sidebar -->
      <div class="chat-sidebar">
        <ChatList @edit-profile="handleEditProfile" @settings="handleSettings" @developer-info="handleDeveloperInfo" />
      </div>

      <!-- Main chat area -->
      <div class="chat-main">
        <ChatWindow @clear-messages="showClearMessagesConfirm = true" />
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
      <ChatList @edit-profile="handleEditProfile" @settings="handleSettings" @developer-info="handleDeveloperInfo" />
    </div>

    <!-- Chat Window View -->
    <div v-else class="mobile-chat-window">
      <div class="mobile-chat-header">
        <button class="back-button" @click="goBackToList">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
            <path d="M15 18L9 12L15 6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </button>
        <h2>{{ selectedChat?.name || '' }}</h2>
        <button class="clear-messages-button" @click="showClearMessagesConfirm = true" title="清除聊天记录">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
            <path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2m3 0v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6h14zM10 11v6M14 11v6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </button>
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

  <!-- Developer Info Modal -->
  <DeveloperInfoModal
    v-if="showDeveloperInfoModal"
    :show="showDeveloperInfoModal"
    @close="handleDeveloperInfoClose"
  />

  <!-- Clear Messages Confirmation Dialog -->
  <div v-if="showClearMessagesConfirm" class="modal-overlay" @click="showClearMessagesConfirm = false">
    <div class="modal-content confirm-dialog" @click.stop>
      <div class="modal-header">
        <h3>确认清除聊天记录</h3>
      </div>

      <div class="modal-body">
        <p class="confirm-text">
          确定要清除与 <strong>{{ selectedChat?.name }}</strong> 的所有聊天记录吗？
        </p>
      </div>

      <div class="modal-footer">
        <button @click="showClearMessagesConfirm = false" class="btn btn-secondary">
          取消
        </button>
        <button @click="handleClearMessages" class="btn btn-danger" :disabled="isClearing">
          {{ isClearing ? '清除中...' : '确定清除' }}
        </button>
      </div>
    </div>
  </div>

</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue';
import ChatList from '../components/ChatList.vue';
import ChatWindow from '../components/ChatWindow.vue';
import ProfileEditModal from '../components/ProfileEditModal.vue';
import SettingsModal from '../components/SettingsModal.vue';
import DeveloperInfoModal from '../components/DeveloperInfoModal.vue';

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
const showDeveloperInfoModal = ref(false);
const showClearMessagesConfirm = ref(false);
const isClearing = ref(false);

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

const handleDeveloperInfo = () => {
  showDeveloperInfoModal.value = true;
};

const handleDeveloperInfoClose = () => {
  showDeveloperInfoModal.value = false;
};

// Handle clear messages
const handleClearMessages = async () => {
  if (isClearing.value || !selectedChatId.value) return;

  isClearing.value = true;

  try {
    const success = chatStore.clearContactChat(selectedChatId.value);

    if (success) {
      showClearMessagesConfirm.value = false;

      // Go back to chat list on mobile, or clear selection on desktop
      if (isMobile.value) {
        goBackToList();
      } else {
        chatStore.selectChat(null);
      }
    } else {
      console.error('Failed to clear messages: operation returned false');
    }
  } catch (error) {
    console.error('Failed to clear messages:', error);
  } finally {
    isClearing.value = false;
  }
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
  width: 100vw;
  height: 100vh;
  background-color: var(--color-bg-primary);
  overflow: hidden; /* Prevent page scrolling */
  position: fixed; /* Fix to viewport */
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
}

.mobile-chat-list {
  width: 100%;
  height: 100vh;
  display: flex;
  flex-direction: column;
  overflow: hidden; /* Prevent page scrolling */
  padding-top: 60px; /* Space for fixed header */
}

.mobile-header {
  background-color: var(--color-bg-tertiary);
  border-bottom: var(--border-width) solid var(--color-border);
  padding: var(--spacing-xl);
  display: flex;
  align-items: center;
  justify-content: center;
  position: fixed; /* Change from sticky to fixed */
  top: 0;
  left: 0;
  right: 0;
  z-index: 10;
  height: 60px; /* Slightly larger height for mobile */
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
  padding: var(--spacing-xl);
  display: flex;
  align-items: center;
  justify-content: space-between;
  position: fixed; /* Change from sticky to fixed */
  top: 0;
  left: 0;
  right: 0;
  z-index: 10;
  height: 60px; /* Fixed height for header */
}

.back-button {
  background: none;
  border: none;
  color: var(--color-text-primary);
  cursor: pointer;
  padding: var(--spacing-lg);
  border-radius: var(--radius-lg); /* Use proper radius variable */
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background-color 0.2s;
  min-width: 38px; /* Adjusted for mobile */
  min-height: 38px;
  touch-action: manipulation;
  -webkit-tap-highlight-color: transparent;
  user-select: none;
  -webkit-user-select: none;
  -moz-user-select: none;
  -ms-user-select: none;
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
  text-align: center;
}

.clear-messages-button {
  width: var(--button-height-md);
  height: var(--button-height-md);
  background: var(--color-bg-secondary);
  border: var(--border-width) solid var(--color-border);
  color: var(--color-text-secondary);
  cursor: pointer;
  padding: 0;
  border-radius: var(--radius-full);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
  flex-shrink: 0;
  box-shadow: var(--shadow-xs);
  touch-action: manipulation;
  -webkit-tap-highlight-color: transparent;
  user-select: none;
  -webkit-user-select: none;
  -moz-user-select: none;
  -ms-user-select: none;
}

.clear-messages-button:hover {
  background-color: var(--color-bg-tertiary);
  color: var(--color-error);
  box-shadow: var(--shadow-sm);
}

/* Modal styles */
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
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-xl);
  border: var(--border-width) solid var(--color-border);
  width: 90%;
  max-width: 400px;
  max-height: 80vh;
  overflow-y: auto;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-3xl);
  padding-bottom: var(--spacing-xl);
}

.modal-header h3 {
  margin: 0;
  color: var(--color-text-primary);
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
}

.modal-body {
  padding: 0 var(--spacing-3xl) var(--spacing-xl);
}

.modal-footer {
  padding: var(--spacing-xl) var(--spacing-3xl);
  display: flex;
  justify-content: flex-end;
  gap: var(--spacing-lg);
}

.confirm-text {
  margin: 0;
  color: var(--color-text-primary);
  font-size: var(--font-size-base);
  line-height: 1.5;
}

.btn {
  padding: var(--spacing-lg) var(--spacing-xl);
  border: none;
  border-radius: var(--radius-lg);
  cursor: pointer;
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-medium);
  transition: all 0.15s ease;
  height: var(--button-height-md);
}

.btn-secondary {
  background-color: var(--color-bg-secondary);
  color: var(--color-text-primary);
  border: var(--border-width) solid var(--color-border);
}

.btn-secondary:hover {
  background-color: var(--color-bg-tertiary);
}

.btn-danger {
  background-color: var(--color-error);
  color: white;
}

.btn-danger:hover {
  background-color: #dc2626; /* Darker red on hover */
}

.btn-danger:disabled {
  background-color: var(--color-bg-secondary);
  color: var(--color-text-secondary);
  cursor: not-allowed;
}


</style>