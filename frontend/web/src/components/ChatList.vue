<template>
  <div class="chat-list-container">
    <div class="list-header">
      <h2>会话列表</h2>
      <div class="header-right">
        <div class="contact-limits">
          联系人 {{ chatStore.contactLimits.current_count }}/{{ chatStore.contactLimits.contact_limit }}
        </div>
        <button
          class="add-contact-btn"
          @click="handleAddContact"
          :disabled="!chatStore.contactLimits.can_add_more"
          :title="chatStore.contactLimits.can_add_more ? '添加联系人' : '联系人数量已达上限'"
        >
          +
        </button>
      </div>
    </div>
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
      <span class="emoji-large">📝</span>
      <p>暂无会话</p>
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
import { ref } from 'vue';
import { useChatStore } from '../stores/chat';
import { useToast } from 'vue-toastification';
import ContactSearchModal from './ContactSearchModal.vue';
import ContactAvatar from './ContactAvatar.vue';

const chatStore = useChatStore();
const toast = useToast();
const showSearchModal = ref(false);

const handleAddContact = () => {
  // Check if user has reached contact limit
  if (!chatStore.contactLimits.can_add_more) {
    toast.error('联系人数量已达上限');
    return;
  }

  // Show search modal
  showSearchModal.value = true;
};

const handleSearchModalClose = () => {
  showSearchModal.value = false;
};

const handleContactAdded = () => {
  // Refresh contacts after adding
  chatStore.fetchContacts();
  showSearchModal.value = false;
  toast.success('联系人添加成功');
};
</script>

<style scoped>
.chat-list-container {
  display: flex;
  flex-direction: column;
  background-color: var(--color-bg-secondary);
  height: 100%;
  border-radius: var(--border-radius);
  overflow: hidden;
}

.list-header {
  padding: var(--spacing-lg) var(--spacing-2xl);
  border-bottom: var(--border-width) solid var(--color-border);
  background-color: var(--color-bg-secondary);
  position: sticky;
  top: 0;
  z-index: 5;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.list-header h2 {
  margin: 0;
  font-size: 1.1rem;
  font-weight: 500;
}

.header-right {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
}

.contact-limits {
  font-size: 0.85rem;
  color: var(--color-text-secondary);
  background-color: var(--color-bg-primary);
  padding: var(--spacing-xs) var(--spacing-sm);
  border-radius: 12px;
  border: 1px solid var(--color-border);
}

.add-contact-btn {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  border: 1px solid var(--color-border);
  background-color: var(--color-bg-primary);
  color: var(--color-text-primary);
  font-size: 1.2rem;
  font-weight: 500;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.add-contact-btn:hover:not(:disabled) {
  background-color: var(--color-accent);
  color: white;
  border-color: var(--color-accent);
}

.add-contact-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

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
  padding: var(--spacing-md) var(--spacing-lg);
  cursor: pointer;
  border-bottom: var(--border-width) solid var(--color-border);
  transition: background-color 0.2s;
  background-color: var(--color-bg-secondary);
}

.chat-item:hover {
  background-color: var(--color-bg-primary);
}

.chat-item.active {
  background-color: var(--color-accent-soft);
}

.chat-item-content {
  flex-grow: 1;
  overflow: hidden;
  padding: 0 var(--spacing-sm);
}

.chat-item-name {
  font-weight: 500;
  color: var(--color-text-primary);
  margin-bottom: 4px;
}

.chat-item-preview {
  font-size: 0.85rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: var(--color-text-secondary);
}

.no-chats-placeholder {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  height: 100%;
  color: var(--color-text-secondary);
  text-align: center;
  padding: var(--spacing-lg);
}

.emoji-large {
  font-size: 3rem;
  margin-bottom: var(--spacing-lg);
}
</style> 