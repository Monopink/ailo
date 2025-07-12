<template>
  <div
    class="message-bubble"
    :class="[
      `message-${message.sender}`,
      `status-${message.status || 'sent'}`,
      { 'can-retry': canRetry }
    ]"
    role="article"
    :aria-label="getMessageAriaLabel()">
    <div class="message-content">
      <p>{{ message.text }}</p>

      <!-- WeChat-style status indicators -->
      <div class="message-status" v-if="showStatus">
        <!-- Failed indicator - red exclamation mark like WeChat -->
        <button
          v-if="isFailedStatus"
          class="status-indicator failed"
          @click="handleRetry"
          type="button"
          :disabled="retrying"
          :aria-label="retrying ? '正在重试发送消息' : '重试发送消息'"
          :title="retrying ? '正在重试...' : '点击重试发送'">
          <div class="error-icon" aria-hidden="true">!</div>
          <span class="sr-only">{{ retrying ? '正在重试发送消息' : '消息发送失败，点击重试' }}</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { MessageStatus } from '../services/messaging/types'
import { uiLogger } from '../utils/logger.js'
import { handleError } from '../utils/errorHandler.js'

const props = defineProps({
  message: {
    type: Object,
    required: true,
  },
})

const emit = defineEmits(['retry'])

const retrying = ref(false)

// Computed properties
const showStatus = computed(() => {
  return props.message.sender === 'self' && isFailedStatus.value
})

const isFailedStatus = computed(() => {
  return props.message.status === MessageStatus.FAILED ||
         props.message.status === MessageStatus.BLOCKED
})

const canRetry = computed(() => {
  return isFailedStatus.value && props.message.canRetry !== false
})

// Accessibility helpers
const getMessageAriaLabel = () => {
  const senderText = props.message.sender === 'self' ? '我' : '对方'
  const statusText = isFailedStatus.value ? '发送失败' : '已发送'
  const timeText = props.message.timestamp ?
    new Date(props.message.timestamp).toLocaleTimeString() : ''

  return `${senderText}发送的消息：${props.message.text}。状态：${statusText}。${timeText}`
}

// Methods
const handleRetry = async () => {
  if (retrying.value || !canRetry.value) {
    uiLogger.warn('Retry blocked', {
      retrying: retrying.value,
      canRetry: canRetry.value
    })
    return
  }

  retrying.value = true
  uiLogger.debug('Retrying message', {
    localId: props.message.localId,
    text: props.message.text?.substring(0, 50) + '...'
  })

  try {
    await emit('retry', props.message.localId)
    uiLogger.info('Message retry initiated', { localId: props.message.localId })
  } catch (error) {
    uiLogger.error('Message retry failed', {
      localId: props.message.localId,
      error
    })
    handleError(error, {
      operation: 'retry_message',
      context: 'MessageBubble',
      showToast: true,
    })
  } finally {
    retrying.value = false
  }
}
</script>

<style scoped>
.message-bubble {
  display: flex;
  margin-bottom: 0.75rem;
  max-width: 70%;
}

.message-content {
  padding: 0.75rem 1rem;
  border-radius: 18px;
  position: relative;
  min-width: 60px;
  word-break: break-word;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
}

/* Add space for status indicator on sent messages */
.message-self .message-content {
  margin-left: 30px;
}

.message-self {
  align-self: flex-end;
  margin-left: auto;
}

.message-self .message-content {
  background-color: var(--color-sent-message);
  color: var(--color-sent-text);
  border-bottom-right-radius: 5px;
}

.message-other {
  align-self: flex-start;
}

.message-other .message-content {
  background-color: var(--color-received-message);
  color: var(--color-received-text);
  border-bottom-left-radius: 5px;
}

.message-content p {
  margin: 0;
  white-space: pre-wrap; /* Preserve line breaks */
}

/* Message status styles - WeChat style */
.message-status {
  position: absolute;
  left: -25px;
  top: 50%;
  transform: translateY(-50%);
  display: flex;
  align-items: center;
}

.status-indicator {
  display: flex;
  align-items: center;
  justify-content: center;
  background: none;
  border: none;
  padding: 2px;
  border-radius: 50%;
  transition: background-color 0.2s, box-shadow 0.2s;
}

/* Failed status - red exclamation mark like WeChat */
.status-indicator.failed {
  cursor: pointer;
}

.status-indicator.failed:hover:not(:disabled) {
  background-color: rgba(255, 59, 48, 0.1);
}

.status-indicator.failed:focus {
  outline: none;
}

.status-indicator.failed:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.error-icon {
  width: 18px;
  height: 18px;
  background: var(--color-error);
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: bold;
  transition: transform 0.2s;
}

.error-icon:hover {
  transform: scale(1.1);
}



/* Message bubble status states */
.message-bubble.status-pending .message-content {
  opacity: 0.7;
}

.message-bubble.status-failed .message-content {
  border: 1px solid var(--color-error);
  background-color: var(--color-error-light);
}

.message-bubble.status-blocked .message-content {
  border: 1px solid var(--color-warning);
  background-color: var(--color-warning-light);
}

.message-bubble.can-retry {
  cursor: pointer;
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

/* Responsive adjustments */
@media (max-width: 767px) {
  .message-bubble {
    max-width: 80%;
  }
}
</style> 