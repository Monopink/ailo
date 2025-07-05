<template>
  <div class="chat-window-container" v-if="selectedChat">
    <div class="chat-header">
      <h3 class="chat-title">{{ selectedChat.name }}</h3>
    </div>
    <div class="messages-area" ref="messagesContainer">
      <MessageBubble v-for="message in selectedChat.messages" :key="message.id" :message="message" />
      <!-- Typing indicator -->
      <div v-if="isTyping" class="typing-indicator">
        <div class="typing-bubble">
          <div class="typing-dots">
            <span></span>
            <span></span>
            <span></span>
          </div>
          <span class="typing-text">{{ selectedChat.name }} 正在输入...</span>
        </div>
      </div>
    </div>
    <div class="message-input-area">
      <input
        type="text"
        v-model="newMessage"
        @keyup.enter="sendMessage"
        @input="handleInput"
        placeholder="输入消息..."
        class="message-input"
      />
      <button @click="sendMessage" class="btn send-button">发送</button>
    </div>
  </div>
  <div v-else class="no-chat-selected">
    <div class="empty-state">
      <span class="emoji-large">💬</span>
      <p>选择一个会话开始聊天</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, watch, onMounted, onUnmounted } from 'vue';
import { useChatStore } from '../stores/chat';
import MessageBubble from './MessageBubble.vue';
import { messageService } from '../services/messaging';
import { useAuthStore } from '../stores/auth';
import { MessageType } from '../services/messaging/types';

const chatStore = useChatStore();
const authStore = useAuthStore();
const newMessage = ref('');
const messagesContainer = ref(null);
const isTyping = ref(false);
const typingTimeout = ref(null);

const selectedChat = computed(() => {
  return chatStore.chats.find(chat => chat.id === chatStore.selectedChatId);
});

const chats = computed(() => chatStore.chats);

const scrollToBottom = async () => {
  await nextTick();
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight;
  }
};

watch(() => selectedChat.value?.messages, () => {
  scrollToBottom();
}, { deep: true, immediate: true });

// Handle input changes for typing indicator
const isCurrentlyTyping = ref(false);

const handleInput = async () => {
  if (!selectedChat.value) return;

  const hasContent = newMessage.value.trim().length > 0;

  if (hasContent) {
    // Send typing indicator only when starting to type (not already typing)
    if (!isCurrentlyTyping.value) {
      try {
        await messageService.sendTypingIndicator(selectedChat.value);
        isCurrentlyTyping.value = true;
        console.log('📤 Sent typing indicator (started typing)');
      } catch (error) {
        console.error('Failed to send typing indicator:', error);
      }
    }
  } else {
    // Send typing_end when input is completely cleared
    if (isCurrentlyTyping.value) {
      try {
        await messageService.sendTypingEnd(selectedChat.value);
        isCurrentlyTyping.value = false;
        console.log('📤 Sent typing_end (input cleared)');
      } catch (error) {
        console.error('Failed to send typing end:', error);
      }
    }
  }
};

const sendMessage = async () => {
  if (newMessage.value.trim() === '' || !selectedChat.value) return;

  const content = newMessage.value;
  newMessage.value = '';

  // Reset typing state without sending typing_end (message sending implies typing stopped)
  isCurrentlyTyping.value = false;

  try {
    // Send message using unified message service
    console.log('Sending message to:', selectedChat.value.entity_id);
    await messageService.sendChatMessage(selectedChat.value, content);

    // Add message to local chat (it will also be received via onMessage)
    const userMessage = {
      id: Date.now(),
      text: content,
      sender: 'user',
      timestamp: new Date(),
      messageType: MessageType.CHAT.code
    };

    chatStore.addMessage(selectedChat.value.id, userMessage);
    await nextTick();
    scrollToBottom();
  } catch (error) {
    console.error("Failed to send message to system conversation:", error);
  }
};

// Handle typing messages from global events
const handleTypingMessage = (event) => {
  const { message } = event.detail
  console.log('📨 [ChatWindow] Received typing message:', message)

  // Find the chat that corresponds to this message
  // Try both ways to be compatible with bot and user messages:
  // 1. For bot messages: message.from is entity_id, find by entity_id
  // 2. For user messages: message.from might correspond to chat.id
  const chat = chats.value.find(c => c.entity_id === message.from || c.id === message.from)

  if (!chat) {
    console.warn('📨 [ChatWindow] No chat found for typing message from:', message.from)
    return
  }

  // Only handle typing for the currently selected chat
  if (!selectedChat.value || selectedChat.value.id !== chat.id) {
    return
  }

  if (message.type === 2) { // TYPING
    // Show typing indicator
    isTyping.value = true
    // Clear existing timeout
    if (typingTimeout.value) {
      clearTimeout(typingTimeout.value)
    }
    // Auto-hide typing indicator after 10 seconds
    typingTimeout.value = setTimeout(() => {
      isTyping.value = false
    }, 10000)
  } else if (message.type === 3) { // TYPING_END
    // Hide typing indicator
    isTyping.value = false
    if (typingTimeout.value) {
      clearTimeout(typingTimeout.value)
      typingTimeout.value = null
    }
  }
}

// Handle chat messages to hide typing indicator
const handleChatMessageReceived = (event) => {
  const { message, chatId } = event.detail

  console.log('📨 [ChatWindow] Chat message event received:', {
    chatId,
    selectedChatId: selectedChat.value?.id,
    messageFrom: message.from,
    isTypingActive: isTyping.value
  })

  // Only handle for the currently selected chat
  if (!selectedChat.value || selectedChat.value.id !== chatId) {
    console.log('📨 [ChatWindow] Ignoring chat message - not current chat')
    return
  }

  // Hide typing indicator when receiving any chat message
  console.log('📨 [ChatWindow] Chat message received, hiding typing indicator')
  isTyping.value = false
  if (typingTimeout.value) {
    clearTimeout(typingTimeout.value)
    typingTimeout.value = null
  }
}

onMounted(() => {
  console.log('🔧 [ChatWindow] Component mounted')
  // Listen for typing messages from global events
  window.addEventListener('typing-message', handleTypingMessage)
  // Listen for chat messages to hide typing indicator
  window.addEventListener('chat-message-received', handleChatMessageReceived)
})

onUnmounted(() => {
  console.log('🔧 [ChatWindow] Component unmounted')
  // Remove event listeners
  window.removeEventListener('typing-message', handleTypingMessage)
  window.removeEventListener('chat-message-received', handleChatMessageReceived)
  // Clear typing timeout
  if (typingTimeout.value) {
    clearTimeout(typingTimeout.value)
  }
})
</script>

<style scoped>
.chat-window-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  width: 100%;
  position: relative;
}

.chat-header {
  padding: 1rem 1.5rem;
  border-bottom: var(--border-width) solid var(--color-border);
  background-color: var(--color-bg-secondary);
  border-top-left-radius: var(--border-radius);
  border-top-right-radius: var(--border-radius);
  position: sticky;
  top: 0;
  z-index: 5;
}

.chat-title {
  margin: 0;
  font-size: 1.1rem;
  font-weight: 500;
}

.messages-area {
  flex-grow: 1;
  padding: 1.5rem;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  background-color: var(--color-bg-primary);
  height: calc(100% - 120px);
  /* Subtract header and input height */
}

.message-input-area {
  display: flex;
  padding: 1rem;
  background-color: var(--color-bg-secondary);
  border-top: var(--border-width) solid var(--color-border);
  border-bottom-left-radius: var(--border-radius);
  border-bottom-right-radius: var(--border-radius);
  position: sticky;
  bottom: 0;
  z-index: 5;
}

.message-input {
  flex-grow: 1;
  padding: 0.75rem 1rem;
  border: var(--border-width) solid var(--color-border);
  border-radius: var(--border-radius-sm);
  margin-right: 0.75rem;
  background-color: var(--color-bg-primary);
  color: var(--color-text-primary);
}

.send-button {
  padding: 0.75rem 1.25rem;
  background-color: var(--color-accent);
  color: white;
  border: none;
  white-space: nowrap;
}

.no-chat-selected {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100%;
  width: 100%;
  color: var(--color-text-secondary);
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}

.emoji-large {
  font-size: 3rem;
  margin-bottom: 1rem;
}

/* Responsive adjustments */
@media (max-width: 767px) {
  .message-input-area {
    padding: 0.75rem;
  }

  .message-input {
    padding: 0.5rem;
    font-size: 16px;
    /* Prevent zoom on focus on iOS */
  }

  .send-button {
    padding: 0.5rem 1rem;
  }

  .messages-area {
    padding: 1rem;
  }
}

/* Typing indicator styles */
.typing-indicator {
  display: flex;
  align-items: center;
  margin: 0.5rem 0;
  padding: 0 1rem;
}

.typing-bubble {
  display: flex;
  align-items: center;
  background-color: var(--color-bg-secondary);
  border-radius: var(--border-radius-large);
  padding: 0.75rem 1rem;
  max-width: 200px;
  border: var(--border-width) solid var(--color-border);
}

.typing-dots {
  display: flex;
  gap: 0.25rem;
  margin-right: 0.5rem;
}

.typing-dots span {
  width: 6px;
  height: 6px;
  background-color: var(--color-text-secondary);
  border-radius: 50%;
  animation: typing-bounce 1.4s infinite ease-in-out;
}

.typing-dots span:nth-child(1) {
  animation-delay: -0.32s;
}

.typing-dots span:nth-child(2) {
  animation-delay: -0.16s;
}

.typing-text {
  font-size: 0.875rem;
  color: var(--color-text-secondary);
  font-style: italic;
}

@keyframes typing-bounce {
  0%, 80%, 100% {
    transform: scale(0.8);
    opacity: 0.5;
  }
  40% {
    transform: scale(1);
    opacity: 1;
  }
}
</style>