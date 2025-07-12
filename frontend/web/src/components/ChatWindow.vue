<template>
  <div class="chat-window-container" v-if="selectedChat">
    <div class="chat-header hide-on-mobile">
      <h3 class="chat-title">{{ selectedChat.name }}</h3>
    </div>
    <div
      class="messages-area"
      ref="messagesContainer"
      role="log"
      aria-live="polite"
      aria-label="聊天消息列表"
      tabindex="0">
      <template v-for="(item, index) in messagesWithTimeDividers" :key="item.id || item.localId || `divider-${index}`">
        <TimeDivider v-if="item.type === 'time-divider'" :timestamp="item.timestamp" />
        <SystemMessage v-else-if="item.messageType === MessageType.SYSTEM" :message="item.text" />
        <MessageFailureNotice v-else-if="item.type === 'failure-notice'" :message="item.message" />
        <MessageBubble v-else :message="item" @retry="handleRetry" />
      </template>
      <!-- Typing indicator -->
      <div v-if="isTyping" class="typing-indicator" aria-live="polite">
        <div class="typing-bubble">
          <div class="typing-dots">
            <span></span>
            <span></span>
            <span></span>
          </div>
        </div>
        <span class="sr-only">{{ selectedChat?.name }} 正在输入...</span>
      </div>
    </div>
    <div class="message-input-area" role="form" aria-label="发送消息">
      <label for="message-input" class="sr-only">输入消息内容</label>
      <input
        id="message-input"
        type="text"
        v-model="newMessage"
        @keyup.enter="sendMessage"
        @input="handleInput"
        @compositionstart="handleCompositionStart"
        @compositionend="handleCompositionEnd"
        :maxlength="MessageConstraints.MAX_LENGTH"
        :aria-describedby="messageInputDescription"
        placeholder="输入消息..."
        class="message-input"
        :disabled="!selectedChat"
        aria-required="true"
      />
      <div :id="messageInputDescription" class="sr-only">
        最多可输入 {{ MessageConstraints.MAX_LENGTH }} 个字符，按回车键发送消息
      </div>
      <button
        @click="sendMessage"
        class="btn send-button"
        type="button"
        :disabled="!newMessage.trim() || !selectedChat"
        :aria-label="`发送消息给 ${selectedChat?.name || '联系人'}`">
        发送
      </button>
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
import MessageFailureNotice from './MessageFailureNotice.vue';
import { messageService } from '../services/messaging';
import { useAuthStore } from '../stores/auth';
import { MessageType, MessageConstraints, MessageSecurity } from '../services/messaging/types';
import { messageRateLimiter } from '../services/messaging/rateLimiter';
import { useToast } from 'vue-toastification';
import { notificationService } from '../services/notificationService';
import { MESSAGE_CONFIG } from '../config/constants.js';

const chatStore = useChatStore();
const authStore = useAuthStore();
const toast = useToast();
const newMessage = ref('');
const messagesContainer = ref(null);
const isTyping = ref(false);
const typingTimeout = ref(null);

// Helper function for showing toast messages
const showToast = (message, type = 'error') => {
  toast[type](message);
};

// Generate unique ID for accessibility
const messageInputDescription = ref(`message-input-desc-${Math.random().toString(36).substring(2, 9)}`);

const selectedChat = computed(() => {
  return chatStore.chats.find(chat => chat.id === chatStore.selectedChatId);
});

const chats = computed(() => chatStore.chats);

// Add time dividers and failure notices between messages
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

    // Add failure notice after failed messages
    if (shouldShowFailureNotice(currentMessage)) {
      result.push({
        type: 'failure-notice',
        id: `failure-${currentMessage.localId || currentMessage.id}`,
        message: getFailureMessage(currentMessage)
      });
    }
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

// Helper function to determine if we should show a failure notice
const shouldShowFailureNotice = (message) => {
  // Show notice for failed or blocked self messages (messages sent by current user)
  return message.sender === 'self' &&
         (message.status === 3 || message.status === 4); // FAILED or BLOCKED
};

// Helper function to get failure message text
const getFailureMessage = (message) => {
  if (message.status === 4) { // BLOCKED
    // For blocked messages, prioritize system message, then default
    return message.systemMessage || '消息被系统屏蔽';
  } else if (message.status === 3) { // FAILED
    // For failed messages, prioritize system message, then map by failure reason
    if (message.systemMessage) {
      return message.systemMessage;
    }

    // Map failure reasons to user-friendly messages (never show provider errors)
    if (message.failureReason === 6) { // NOT_CONTACTS
      return '你还不是对方的联系人';
    } else if (message.failureReason === 3) { // BLOCKED_BY_USER
      return '消息被对方拒收';
    } else if (message.failureReason === 5) { // RATE_LIMITED
      return '发送过于频繁';
    } else if (message.failureReason === 2) { // CONVERSATION_ERROR
      return '连接失败，请检查网络后重试';
    } else if (message.failureReason === 7) { // CONTENT_TOO_LONG
      return '消息内容过长';
    } else {
      return '消息发送失败';
    }
  }
  return '消息发送异常';
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
// Use configured typing delay
const TYPING_DELAY = MESSAGE_CONFIG.TYPING_DELAY;

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
        // Check if message service is available and initialized
        if (messageService && typeof messageService.sendTypingIndicator === 'function') {
          await messageService.sendTypingIndicator(selectedChat.value);
          isCurrentlyTyping.value = true;
        } else {
          console.warn('Message service not available for typing indicator');
        }
      } catch (error) {
        console.error('Failed to send typing indicator:', error);
        // Don't throw error, just log it as typing indicator is not critical
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

  const content = newMessage.value.trim();

  // Sanitize content for validation
  const sanitizedContent = MessageSecurity.sanitizeContent(content);

  // Check message length
  if (sanitizedContent.length > MessageConstraints.MAX_LENGTH) {
    showToast(`消息长度不能超过 ${MessageConstraints.MAX_LENGTH} 个字符`);
    return;
  }

  // Check rate limiting BEFORE sending
  const rateLimitCheck = messageRateLimiter.canSendMessage(sanitizedContent, selectedChat.value.id);
  if (!rateLimitCheck.canSend) {
    const errorMessage = messageRateLimiter.getRateLimitMessage(rateLimitCheck.reason, rateLimitCheck.waitTime);
    showToast(errorMessage);
    return;
  }

  // Clear input only after validation passes
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

  // Send message using unified message service with status management
  try {
    console.log('Sending message to:', selectedChat.value.id);

    // Check if message service is available and initialized
    if (!messageService || typeof messageService.sendChatMessage !== 'function') {
      throw new Error('Message service not available');
    }

    const uiMessage = await messageService.sendChatMessage(selectedChat.value, content);

    // Add UI message to local chat immediately (with pending status)
    chatStore.addMessage(selectedChat.value.id, uiMessage);
  } catch (error) {
    console.error('Failed to send message:', error);

    // Create a failed message for UI feedback
    const failedMessage = {
      id: `failed-${Date.now()}`,
      localId: `local-${Date.now()}`,
      text: content,
      sender: 'self',
      timestamp: new Date(),
      status: 'failed',
      canRetry: true
    };

    // Add failed message to chat
    chatStore.addMessage(selectedChat.value.id, failedMessage);

    // Show user-friendly error message
    showToast('消息发送失败，请重试');
  }
  await nextTick();
  scrollToBottom();

  // Note: No try-catch needed here as the message service handles all errors
  // and updates the message status accordingly. The message will always be
  // displayed in the UI, with appropriate status indicators.
};

// Handle message retry
const handleRetry = async (localId) => {
  try {
    console.log('🔄 [ChatWindow] Retrying message with localId:', localId);
    console.log('🔄 [ChatWindow] LocalId type:', typeof localId);
    await messageService.retryMessage(localId);
  } catch (error) {
    console.error('❌ [ChatWindow] Failed to retry message:', error);
    // Error is handled by the status manager
  }
};



// Handle message status changes
const handleMessageStatusChange = (message) => {
  console.log('📊 Message status changed:', message.localId, message.status);

  // Find and update the message in the chat store
  if (selectedChat.value) {
    // If this is a retry (regardless of current status), move the message to the bottom
    if (message.isRetry) {
      console.log('🔄 Moving retry message to bottom:', message.localId);
      chatStore.moveMessageToBottom(selectedChat.value.id, message.localId, message);

      // Scroll to bottom to show the retried message
      nextTick(() => {
        scrollToBottom();
      });
    } else {
      chatStore.updateMessageStatus(selectedChat.value.id, message.localId, message);
    }
  }
};

// Handle typing messages from global events
const handleTypingMessage = (event) => {
  const { message } = event.detail
  console.log('📨 [ChatWindow] Received typing message:', message)

  // Find the chat that corresponds to this message
  const chat = chats.value.find(c => c.id === message.from)

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
    // Auto-hide typing indicator after configured duration
    typingTimeout.value = setTimeout(() => {
      isTyping.value = false
    }, MESSAGE_CONFIG.TYPING_AUTO_HIDE_DURATION)
  } else if (message.type === 3) { // TYPING_END
    // Hide typing indicator
    isTyping.value = false
    if (typingTimeout.value) {
      clearTimeout(typingTimeout.value)
      typingTimeout.value = null
    }
  }
}

// Handle incoming chat messages
const handleChatMessageReceived = async (event) => {
  const { message } = event.detail

  console.log('📨 [ChatWindow] Received message event:', message)

  // Hide typing indicator when receiving any chat message
  isTyping.value = false
  if (typingTimeout.value) {
    clearTimeout(typingTimeout.value)
    typingTimeout.value = null
  }

  console.log('🔍 [ChatWindow] Looking for chat with message.from:', message.from)
  console.log('🔍 [ChatWindow] Current user id:', authStore.user?.id)
  console.log('🔍 [ChatWindow] Available chats:', chats.value.map(c => ({ id: c.id, name: c.name })))

  // Find the chat that corresponds to this conversation
  let chat = chats.value.find(c => c.id === message.from)

  // Debug: Check system message conditions
  console.log('🔍 [ChatWindow] System message check:', {
    chatFound: !!chat,
    messageType: message.type,
    messageAction: message.content?.action,
    shouldRefresh: !chat && message.type === 9 && message.content?.action === 2
  })

  // If this is a system message about adding contact and we can't find the chat,
  // refresh contacts and try again
  if (!chat && message.type === 9 && message.content?.action === 2) {
    console.log('🔄 [ChatWindow] System message for new contact, refreshing contacts...')
    await chatStore.fetchContacts()
    chat = chats.value.find(c => c.id === message.from)
    console.log('🔄 [ChatWindow] After refresh, found chat:', chat ? { id: chat.id, name: chat.name } : 'null')
    console.log('🔄 [ChatWindow] Available chats after refresh:', chats.value.map(c => ({ id: c.id, name: c.name })))
  }

  console.log('🔍 [ChatWindow] Found chat:', chat ? { id: chat.id, name: chat.name } : 'null')

  if (chat) {
    // Create a UI message object for display
    const uiMessage = {
      id: Date.now() + Math.random(), // Unique ID for received messages
      localId: null, // Received messages don't have localId
      text: message.content,
      sender: message.from === authStore.user?.id ? 'self' : 'other',
      timestamp: new Date(message.timestamp || Date.now()),
      messageType: message.type,
      status: null // Received messages don't have status
    }

    // Add message to chat
    chatStore.addMessage(chat.id, uiMessage)

    // Show browser notification for received messages (only for other users' messages)
    if (uiMessage.sender === 'other' && message.type === MessageType.CHAT) {
      showNotificationForMessage(uiMessage, chat)
    }

    // Scroll to bottom if this is the selected chat
    if (selectedChat.value && selectedChat.value.id === chat.id) {
      nextTick(() => {
        scrollToBottom()
      })
    }

    console.log('✅ [ChatWindow] Added received message to chat:', chat.id)
  } else {
    console.warn('⚠️ [ChatWindow] Could not find chat for received message:', message)
  }
}

// Show browser notification for received message
const showNotificationForMessage = (message, chat) => {
  // Don't show notification if the chat window is currently focused and visible
  if (selectedChat.value && selectedChat.value.id === chat.id && document.hasFocus()) {
    console.log('📢 [ChatWindow] Skipping notification - chat is currently active')
    return
  }

  // Show notification
  notificationService.showMessageNotification(message, chat.name)
}

// Handle notification click to navigate to chat
const handleNotificationChatClick = (event) => {
  const { chatId } = event.detail
  console.log('📢 [ChatWindow] Notification clicked, navigating to chat:', chatId)

  // Find and select the chat
  const chat = chats.value.find(c => c.id === chatId)
  if (chat) {
    chatStore.selectChat(chat.id)
  }
}

onMounted(() => {
  console.log('🔧 [ChatWindow] Component mounted')
  // Listen for typing messages from global events
  window.addEventListener('typing-message', handleTypingMessage)
  // Listen for chat messages to hide typing indicator
  window.addEventListener('chat-message-received', handleChatMessageReceived)
  // Listen for notification clicks
  window.addEventListener('notification-chat-click', handleNotificationChatClick)

  // Listen for message status changes
  const statusManager = messageService.getStatusManager()
  statusManager.onStatusChange(handleMessageStatusChange)
})

onUnmounted(() => {
  console.log('🔧 [ChatWindow] Component unmounted')
  // Remove event listeners
  window.removeEventListener('typing-message', handleTypingMessage)
  window.removeEventListener('chat-message-received', handleChatMessageReceived)
  window.removeEventListener('notification-chat-click', handleNotificationChatClick)

  // Clean up status manager listeners
  const statusManager = messageService.getStatusManager()
  statusManager.offStatusChange(handleMessageStatusChange)

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
  transition: border-color 0.2s, box-shadow 0.2s;
}

.message-input:focus {
  outline: none;
  border-color: var(--color-border);
}

.message-input:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  background-color: var(--color-bg-secondary);
}

.send-button {
  padding: 0.75rem 1.25rem;
  background-color: var(--color-accent);
  color: white;
  border: none;
  border-radius: var(--border-radius-sm);
  white-space: nowrap;
  cursor: pointer;
  transition: background-color 0.2s, box-shadow 0.2s, opacity 0.2s;
}

.send-button:hover:not(:disabled) {
  background-color: var(--color-primary-hover);
}

.send-button:focus {
  outline: none;
}

.send-button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  background-color: var(--color-border);
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
  border: none; /* Remove border from typing indicator */
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

/* Screen reader only content */
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

/* Focus management for messages area */
.messages-area:focus {
  outline: none;
}

</style>