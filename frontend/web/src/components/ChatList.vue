<template>
  <div class="chat-list-container">
    <!-- Top Section: Contact Limits and Add Button -->
    <div class="contact-section">
      <div class="contact-header">
        <span class="contact-title">联系人</span>
        <span class="contact-count">{{ chatStore.contactLimits.current_count }}/{{ chatStore.contactLimits.contact_limit }}</span>
      </div>
      <button
        class="add-contact-btn btn-circle"
        @click="handleAddContact"
        :disabled="!chatStore.contactLimits.can_add_more"
        :title="chatStore.contactLimits.can_add_more ? '添加联系人' : '联系人数量已达上限'"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
          <path d="M12 5v14M5 12h14"/>
        </svg>
      </button>
    </div>

    <!-- Chat List -->
    <ul class="chat-list" v-if="chatStore.chats.length > 0">
      <li
        v-for="chat in chatStore.chats"
        :key="chat.id"
        class="chat-item"
        :class="{ active: chat.id === chatStore.selectedChatId }"
        @click="chatStore.selectChat(chat.id)"
      >
        <ContactAvatar :nickname="chat.name" size="medium" />
        <div class="chat-item-content">
          <div class="chat-item-name">{{ chat.name }}</div>
          <div class="chat-item-preview">
            {{ chat.messages[chat.messages.length - 1]?.text || '暂无消息' }}
          </div>
        </div>
      </li>
    </ul>
    <div v-else class="no-chats-placeholder">
      <p>暂无会话</p>
      <button
        class="btn btn-secondary refresh-btn"
        @click="handleRefreshContacts"
        :disabled="isRefreshing"
      >
        {{ isRefreshing ? '刷新中...' : '刷新联系人' }}
      </button>
    </div>

    <!-- Bottom Section: User Profile and Menu -->
    <div class="user-footer">
      <div class="user-info">
        <ContactAvatar
          :nickname="authStore.user?.nickname || '?'"
          size="medium"
        />
        <div class="user-details">
          <div class="user-name">{{ authStore.user?.nickname || '' }}</div>
        </div>
      </div>

      <div class="dropdown-container" ref="dropdownContainer">
        <button
          class="menu-btn btn-circle"
          @click="toggleDropdown"
          :aria-expanded="isDropdownOpen"
          aria-haspopup="true"
          aria-label="用户菜单"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <circle cx="12" cy="12" r="1"/>
            <circle cx="19" cy="12" r="1"/>
            <circle cx="5" cy="12" r="1"/>
          </svg>
        </button>

        <div
          v-if="isDropdownOpen"
          class="dropdown-menu glass-panel-sm"
          role="menu"
          aria-labelledby="user-menu-button"
        >
          <button
            role="menuitem"
            @click="handleEditProfile"
            class="menu-item">
            编辑资料
          </button>
          <button
            role="menuitem"
            @click="handleSettings"
            class="menu-item">
            设置
          </button>
          <button
            v-if="showDeveloperInfo"
            role="menuitem"
            @click="handleDeveloperInfo"
            class="menu-item">
            开发者信息
          </button>
          <div class="menu-divider"></div>
          <button
            role="menuitem"
            @click="handleLogout"
            class="menu-item text-error">
            登出
          </button>
        </div>
      </div>
    </div>

    <!-- Contact Search Modal -->
    <ContactSearchModal
      v-if="showSearchModal"
      @close="handleSearchModalClose"
      @contact-added="handleContactAdded"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue';
import { useChatStore } from '../stores/chat';
import { useAuthStore } from '../stores/auth';
import { useRouter } from 'vue-router';
import { useToast } from 'vue-toastification';
import ContactSearchModal from './ContactSearchModal.vue';
import ContactAvatar from './ContactAvatar.vue';

const chatStore = useChatStore();
const authStore = useAuthStore();
const router = useRouter();
const toast = useToast();
const showSearchModal = ref(false);
const isDropdownOpen = ref(false);
const dropdownContainer = ref(null);
const isRefreshing = ref(false);
const lastRefreshTime = ref(0);
const REFRESH_COOLDOWN = 3000; // 3 seconds cooldown

// Define emits
const emit = defineEmits(['edit-profile', 'settings', 'developer-info']);

// Check if developer info should be shown
const showDeveloperInfo = computed(() => {
  return import.meta.env.VITE_DEV_SHOW_DEVELOPER_INFO === 'true' || import.meta.env.DEV
});

// Dropdown menu handlers
const toggleDropdown = () => {
  isDropdownOpen.value = !isDropdownOpen.value;
};

const closeDropdown = () => {
  isDropdownOpen.value = false;
};

const handleEditProfile = () => {
  closeDropdown();
  emit('edit-profile');
};

const handleSettings = () => {
  closeDropdown();
  emit('settings');
};

const handleDeveloperInfo = () => {
  closeDropdown();
  emit('developer-info');
};

const handleLogout = () => {
  closeDropdown();
  authStore.logout();
  router.push('/login');
};

// Contact management
const handleAddContact = () => {
  if (!chatStore.contactLimits.can_add_more) {
    toast.error('联系人数量已达上限');
    return;
  }
  showSearchModal.value = true;
};

const handleSearchModalClose = () => {
  showSearchModal.value = false;
};

const handleContactAdded = () => {
  chatStore.fetchContacts();
  showSearchModal.value = false;
  toast.success('申请已发送');
};

// Refresh contacts list with frequency control
const handleRefreshContacts = async () => {
  const now = Date.now();

  // Check if already refreshing or within cooldown period
  if (isRefreshing.value || (now - lastRefreshTime.value < REFRESH_COOLDOWN)) {
    return; // Silently ignore frequent clicks
  }

  isRefreshing.value = true;
  lastRefreshTime.value = now;

  try {
    await chatStore.fetchContacts();
    toast.success('联系人列表已刷新');
  } catch (error) {
    toast.error('刷新失败，请稍后重试');
  } finally {
    isRefreshing.value = false;
  }
};

// Click outside to close dropdown
const handleClickOutside = (event) => {
  if (dropdownContainer.value && !dropdownContainer.value.contains(event.target)) {
    closeDropdown();
  }
};

onMounted(() => {
  document.addEventListener('click', handleClickOutside);
});

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside);
});
</script>

<style scoped>
.chat-list-container {
  display: flex;
  flex-direction: column;
  background-color: var(--color-bg-secondary);
  height: 100%;
  overflow: hidden;
}

/* User Footer */
.user-footer {
  padding: var(--spacing-lg) var(--spacing-xl);
  background-color: var(--color-bg-tertiary);
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: auto;
}

.user-info {
  display: flex;
  align-items: center;
  gap: var(--spacing-lg);
  flex: 1;
  min-width: 0;
}

.user-details {
  flex: 1;
  min-width: 0;
}

.user-name {
  font-size: var(--font-size-md);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.menu-btn {
  background-color: var(--color-bg-secondary);
  color: var(--color-text-secondary);
  border: var(--border-width) solid var(--color-border);
  transition: all 0.15s ease;
}

.menu-btn:hover {
  background-color: var(--color-primary);
  color: var(--color-sent-text);
}

/* Contact Section */
.contact-section {
  padding: var(--spacing-lg) var(--spacing-xl);
  display: flex;
  align-items: center;
  background-color: var(--color-bg-secondary);
  justify-content: space-between;
}

.contact-header {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
}

.contact-title {
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
}

.contact-count {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  font-weight: var(--font-weight-medium);
  background-color: var(--color-bg-tertiary);
  padding: var(--spacing-xs) var(--spacing-md);
  border-radius: 12px;
  border: var(--border-width) solid var(--color-border);
}

.add-contact-btn {
  background-color: var(--color-bg-tertiary);
  color: var(--color-text-secondary);
  border: var(--border-width) solid var(--color-border);
  transition: all 0.15s ease;
}

.add-contact-btn:hover:not(:disabled) {
  background-color: var(--color-primary);
  color: var(--color-sent-text);
}

.add-contact-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* Dropdown Menu */
.dropdown-container {
  position: relative;
}

.dropdown-menu {
  position: absolute;
  bottom: calc(100% + var(--spacing-sm));
  right: 0;
  min-width: 140px;
  z-index: 1000;
  padding: var(--spacing-sm);
}

.menu-item {
  width: 100%;
  padding: var(--spacing-md) var(--spacing-lg);
  border: none;
  background: none;
  color: var(--color-text-primary);
  font-size: var(--font-size-sm);
  text-align: left;
  cursor: pointer;
  border-radius: var(--radius-md);
  transition: background-color 0.15s ease;
}

.menu-item:hover {
  background-color: var(--color-bg-tertiary);
}

.menu-divider {
  height: var(--border-width);
  background-color: var(--color-border);
  margin: var(--spacing-sm) 0;
}

/* Chat List */
.chat-list {
  list-style: none;
  padding: 0;
  margin: 0;
  overflow-y: auto;
  flex-grow: 1;
}

.chat-item {
  display: flex;
  align-items: center;
  padding: var(--spacing-lg) var(--spacing-xl);
  cursor: pointer;
  transition: background-color 0.15s ease;
  background-color: var(--color-bg-secondary);
  border-bottom: var(--border-width) solid var(--color-border-light);
}

.chat-item:hover {
  background-color: var(--color-bg-tertiary);
}

.chat-item.active {
  background-color: var(--color-bg-quaternary);
}

.chat-item-content {
  flex-grow: 1;
  overflow: hidden;
  padding-left: var(--spacing-lg);
  min-width: 0;
}

.chat-item-name {
  font-weight: var(--font-weight-medium);
  color: var(--color-text-primary);
  margin-bottom: var(--spacing-xs);
  font-size: var(--font-size-sm);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.chat-item-preview {
  font-size: var(--font-size-xs);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: var(--color-text-tertiary);
  line-height: 1.3;
}

/* Empty State */
.no-chats-placeholder {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  height: 100%;
  color: var(--color-text-tertiary);
  text-align: center;
  padding: var(--spacing-3xl);
}



.no-chats-placeholder p {
  margin: 0 0 var(--spacing-xl) 0;
}

.refresh-btn {
  margin-top: var(--spacing-lg);
  min-width: 120px;
}

/* Mobile Layout Styles */
@media (max-width: 768px) {
  .chat-list-container {
    background-color: var(--color-bg-primary);
  }

  .contact-section {
    background-color: var(--color-bg-primary);
  }

  .chat-list {
    background-color: var(--color-bg-primary);
  }

  .chat-item {
    background-color: var(--color-bg-primary);
  }

  .chat-item:hover {
    background-color: var(--color-bg-secondary);
  }

  .no-chats-placeholder {
    background-color: var(--color-bg-primary);
  }
}
</style>