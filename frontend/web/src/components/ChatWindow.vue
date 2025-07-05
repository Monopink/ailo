<template>
  <div class="chat-window-container" v-if="selectedChat">
    <div class="chat-header hide-on-mobile">
      <h3 class="chat-title">{{ selectedChat.name }}</h3>
    </div>
    <div class="messages-area" ref="messagesContainer">
      <template v-for="(item, index) in messagesWithTimeDividers" :key="item.id || `divider-${index}`">
        <TimeDivider v-if="item.type === 'time-divider'" :timestamp="item.timestamp" />
        <SystemMessage v-else-if="item.type === 'system'" :message="item.text" />
        <MessageBubble v-else :message="item" />
      </template>
      <!-- Typing indicator -->
      <div v-if="isTyping" class="typing-indicator">
        <div class="typing-bubble">
          <div class="typing-dots">
            <span></span>
            <span></span>
            <span></span>
          </div>
        </div>
      </div>
    </div>
    <div class="message-input-area">
      <input
        type="text"
        v-model="newMessage"
        @keyup.enter="sendMessage"
        @input="handleInput"
        @compositionstart="handleCompositionStart"
        @compositionend="handleCompositionEnd"
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
import SystemMessage from './SystemMessage.vue';
import TimeDivider from './TimeDivider.vue';
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

// Add time dividers between messages
const messagesWithTimeDividers = computed(() => {
  if (!selectedChat.value?.messages) return [];

  const messages = selectedChat.value.messages;
  const result = [];

  for (let i = 0; i < messages.length; i++) {
    const currentMessage = messages[i];
    const previousMessage = messages[i - 1];

    // Add time divider if needed
    if (shouldShowTimeDivider(currentMessage, previousMessage)) {
      result.push({
        type: 'time-divider',
        id: `time-${i}`,
        timestamp: currentMessage.timestamp
      });
    }

    result.push(currentMessage);
  }

  return result;
});

// Helper function to determine if we should show a time divider
const shouldShowTimeDivider = (currentMessage, previousMessage) => {
  if (!previousMessage) return true; // Always show for first message

  const current = new Date(currentMessage.timestamp);
  const previous = new Date(previousMessage.timestamp);

  // Show divider if messages are more than 5 minutes apart
  const timeDiff = current.getTime() - previous.getTime();
  return timeDiff > 5 * 60 * 1000; // 5 minutes in milliseconds
};

const scrollToBottom = async () => {
  await nextTick();
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight;
  }
};

// Watch for message changes and typing indicator changes to scroll to bottom
watch(() => selectedChat.value?.messages, () => {
  scrollToBottom();
}, { deep: true, immediate: true });

watch(() => isTyping.value, () => {
  scrollToBottom();
});

// Clear typing state when switching chats
watch(() => selectedChat.value?.id, (newChatId, oldChatId) => {
  if (newChatId !== oldChatId) {
    // Clear typing state for previous chat
    isTyping.value = false;
    isCurrentlyTyping.value = false;
    if (typingTimeout.value) {
      clearTimeout(typingTimeout.value);
      typingTimeout.value = null;
    }
  }
});

// Handle input changes for typing indicator with Chinese input support
const isCurrentlyTyping = ref(false);
const isComposing = ref(false);
const typingTimer = ref(null);
const typingEndTimer = ref(null);
const TYPING_DELAY = 500; // 0.5 seconds delay

// Chinese input method event handlers
const handleCompositionStart = () => {
  isComposing.value = true;
  scheduleTypingStart(); // Schedule typing when composition starts
};

const handleCompositionEnd = () => {
  isComposing.value = false;
  // Check content after composition ends
  if (!newMessage.value.trim()) {
    scheduleTypingEnd(); // Schedule typing_end if content is empty
  }
};

// Schedule typing with delay
const scheduleTypingStart = () => {
  // Cancel any pending typing_end
  if (typingEndTimer.value) {
    clearTimeout(typingEndTimer.value);
    typingEndTimer.value = null;
  }

  // Cancel any previous typing timer
  if (typingTimer.value) {
    clearTimeout(typingTimer.value);
  }

  // Schedule typing after delay
  typingTimer.value = setTimeout(async () => {
    if (!isCurrentlyTyping.value && selectedChat.value) {
      try {
        await messageService.sendTypingIndicator(selectedChat.value);
        isCurrentlyTyping.value = true;
      } catch (error) {
        console.error('Failed to send typing indicator:', error);
      }
    }
    typingTimer.value = null;
  }, TYPING_DELAY);
};

// Schedule typing_end with delay
const scheduleTypingEnd = () => {
  // Cancel any pending typing
  if (typingTimer.value) {
    clearTimeout(typingTimer.value);
    typingTimer.value = null;
  }

  // Cancel any previous typing_end timer
  if (typingEndTimer.value) {
    clearTimeout(typingEndTimer.value);
  }

  // Schedule typing_end after delay
  typingEndTimer.value = setTimeout(async () => {
    if (isCurrentlyTyping.value && selectedChat.value) {
      try {
        await messageService.sendTypingEnd(selectedChat.value);
        isCurrentlyTyping.value = false;
      } catch (error) {
        console.error('Failed to send typing end:', error);
      }
    }
    typingEndTimer.value = null;
  }, TYPING_DELAY);
};

// Input event handler
const handleInput = () => {
  if (!selectedChat.value) return;
  if (isComposing.value) return; // Skip during Chinese input composition

  const hasContent = newMessage.value.trim().length > 0;

  if (hasContent) {
    scheduleTypingStart();
  } else {
    scheduleTypingEnd();
  }
};

const sendMessage = async () => {
  if (newMessage.value.trim() === '' || !selectedChat.value) return;

  const content = newMessage.value;
  newMessage.value = '';

  // Cancel any pending typing timers
  if (typingTimer.value) {
    clearTimeout(typingTimer.value);
    typingTimer.value = null;
  }
  if (typingEndTimer.value) {
    clearTimeout(typingEndTimer.value);
    typingEndTimer.value = null;
  }

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
  const { chatId } = event.detail

  // Only handle for the currently selected chat
  if (!selectedChat.value || selectedChat.value.id !== chatId) {
    return
  }

  // Hide typing indicator when receiving any chat message
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
  // Clear typing timers
  if (typingTimer.value) {
    clearTimeout(typingTimer.value)
  }
  if (typingEndTimer.value) {
    clearTimeout(typingEndTimer.value)
  }
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

/* Hide on mobile utility class */
.hide-on-mobile {
  display: block;
}

/* Responsive adjustments */
@media (max-width: 767px) {
  .hide-on-mobile {
    display: none !important;
  }

  .chat-window-container {
    height: 100vh;
    max-height: 100vh;
  }

  .message-input-area {
    padding: 0.75rem;
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    z-index: 10;
  }

  .messages-area {
    padding: 1rem;
    padding-bottom: 80px; /* Space for fixed input area */
  }

  .message-input {
    padding: 0.5rem;
    font-size: 16px;
    /* Prevent zoom on focus on iOS */
  }

  .send-button {
    padding: 0.5rem 1rem;
  }
}

/* Typing indicator styles - styled like message bubbles */
.typing-indicator {
  display: flex;
  justify-content: flex-start;
  margin: 0.5rem 0;
  padding: 0;
}

.typing-bubble {
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: var(--color-bg-secondary);
  border-radius: 18px;
  padding: 12px 16px;
  min-width: 60px;
  max-width: 200px;
  border: var(--border-width) solid var(--color-border);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
}

.typing-dots {
  display: flex;
  gap: 4px;
  align-items: center;
}

.typing-dots span {
  width: 8px;
  height: 8px;
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