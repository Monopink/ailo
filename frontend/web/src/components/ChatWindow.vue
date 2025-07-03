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
import { sendMessage as sendLCMessage, sendMessageToSystemConversation, onMessage, offMessage, sendTypingIndicator, sendTypingEndIndicator } from '../services/leanmessage';
import { useAuthStore } from '../stores/auth';
import { MessageType } from '../utils/messageTypes';

const chatStore = useChatStore();
const authStore = useAuthStore();
const newMessage = ref('');
const messagesContainer = ref(null);
const isTyping = ref(false);
const typingTimeout = ref(null);
const inputTimeout = ref(null);

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

const handleInput = () => {
  if (!selectedChat.value) return;

  // Clear existing timeout
  if (inputTimeout.value) {
    clearTimeout(inputTimeout.value);
  }

  // Send typing indicator if user is typing and not already typing
  if (newMessage.value.trim().length > 0) {
    if (!isCurrentlyTyping.value) {
      sendTypingIndicator(selectedChat.value.id);
      isCurrentlyTyping.value = true;
    }

    // Send typing end after 3 seconds of no input
    inputTimeout.value = setTimeout(() => {
      if (isCurrentlyTyping.value) {
        sendTypingEndIndicator(selectedChat.value.id);
        isCurrentlyTyping.value = false;
      }
    }, 3000);
  } else {
    // Send typing end immediately if input is empty
    if (isCurrentlyTyping.value) {
      sendTypingEndIndicator(selectedChat.value.id);
      isCurrentlyTyping.value = false;
    }
  }
};

const sendMessage = async () => {
  if (newMessage.value.trim() === '' || !selectedChat.value) return;

  const content = newMessage.value;
  newMessage.value = '';

  // Clear typing timeout and send typing end
  if (inputTimeout.value) {
    clearTimeout(inputTimeout.value);
    inputTimeout.value = null;
  }
  if (isCurrentlyTyping.value) {
    sendTypingEndIndicator(selectedChat.value.id);
    isCurrentlyTyping.value = false;
  }

  try {
    // Check if we have a valid LeanCloud conversation ID
    const conversationId = selectedChat.value.leancloud_conversation_id;
    if (!conversationId || conversationId === selectedChat.value.entity_id) {
      console.warn('⚠️ No valid LeanCloud conversation ID for chat:', selectedChat.value.entity_id);
      throw new Error('No valid conversation ID available for this chat');
    }

    // Send message to system conversation using LeanCloud conversation ID
    console.log('Sending message to system conversation:', conversationId);
    await sendMessageToSystemConversation(conversationId, content);

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

// Handle incoming messages
const handleIncomingMessage = (message, conversation) => {
  console.log('📨 [ChatWindow] Received message:', message);
  console.log('📨 [ChatWindow] Available chats:', chats.value.map(c => ({ id: c.id, name: c.name })));

  // Find the chat that corresponds to this conversation
  const chat = chats.value.find(c => c.id === message.from);
  console.log('📨 [ChatWindow] Found chat:', chat);
  if (!chat) {
    console.warn('📨 [ChatWindow] No chat found for message.from:', message.from);
    return;
  }

  // Handle different message types
  if (message.isTyping) {
    // Show typing indicator
    if (selectedChat.value && selectedChat.value.id === chat.id) {
      isTyping.value = true;
      // Clear existing timeout
      if (typingTimeout.value) {
        clearTimeout(typingTimeout.value);
      }
      // Auto-hide typing indicator after 10 seconds
      typingTimeout.value = setTimeout(() => {
        isTyping.value = false;
      }, 10000);
    }
    return;
  }

  if (message.isTypingEnd) {
    // Hide typing indicator
    if (selectedChat.value && selectedChat.value.id === chat.id) {
      isTyping.value = false;
      if (typingTimeout.value) {
        clearTimeout(typingTimeout.value);
        typingTimeout.value = null;
      }
    }
    return;
  }

  // Hide typing indicator when receiving any content message
  if (message.isContent && selectedChat.value && selectedChat.value.id === chat.id) {
    isTyping.value = false;
    if (typingTimeout.value) {
      clearTimeout(typingTimeout.value);
      typingTimeout.value = null;
    }
  }

  // Only add content messages to chat history
  if (message.isContent) {
    const newMessage = {
      id: message.id,
      text: message.text,
      sender: message.isSystem ? 'system' : 'bot',
      timestamp: new Date(message.timestamp),
      messageType: message.messageType
    };

    chatStore.addMessage(chat.id, newMessage);

    // Scroll to bottom if this is the selected chat
    if (selectedChat.value && selectedChat.value.id === chat.id) {
      nextTick(() => scrollToBottom());
    }
  }
};

onMounted(() => {
  console.log('🔧 [ChatWindow] Component mounted, setting up message listener...');

  // Add a delay to ensure LeanCloud client is ready
  setTimeout(() => {
    console.log('🔧 [ChatWindow] Setting up message listener after delay...');
    onMessage(handleIncomingMessage);
  }, 1000);
});

onUnmounted(() => {
  // Remove message listener
  offMessage(handleIncomingMessage);
});
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