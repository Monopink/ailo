<template>
  <div class="chat-list-container">
    <div class="list-header">
      <h2>会话列表</h2>
    </div>
    <ul class="chat-list" v-if="chatStore.chats.length > 0">
      <li
        v-for="chat in chatStore.chats"
        :key="chat.id"
        class="chat-item"
        :class="{ active: chat.id === chatStore.selectedChatId }"
        @click="chatStore.selectChat(chat.id)"
      >
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
  </div>
</template>

<script setup>
import { useChatStore } from '../stores/chat';

const chatStore = useChatStore();
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
  padding: 1rem 1.5rem;
  border-bottom: var(--border-width) solid var(--color-border);
  background-color: var(--color-bg-secondary);
  position: sticky;
  top: 0;
  z-index: 5;
}

.list-header h2 {
  margin: 0;
  font-size: 1.1rem;
  font-weight: 500;
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
  padding: 0.8rem 1rem;
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
  padding: 0 0.5rem;
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
  padding: 1rem;
}

.emoji-large {
  font-size: 3rem;
  margin-bottom: 1rem;
}
</style> 