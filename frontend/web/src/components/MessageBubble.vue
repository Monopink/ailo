<template>
  <div class="message-bubble" :class="[
    `message-${message.sender}`,
    `status-${message.status || 'sent'}`,
    { 'can-retry': canRetry }
  ]">
    <div class="message-content">
      <p>{{ message.text }}</p>

      <!-- WeChat-style status indicators -->
      <div class="message-status" v-if="showStatus">
        <!-- Failed indicator - red exclamation mark like WeChat -->
        <div v-if="isFailedStatus" class="status-indicator failed" @click="handleRetry">
          <div class="error-icon">!</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { MessageStatus } from '../services/messaging/types'

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
  return props.message.sender === 'user' && isFailedStatus.value
})

const isFailedStatus = computed(() => {
  return props.message.status === MessageStatus.FAILED ||
         props.message.status === MessageStatus.BLOCKED
})

const canRetry = computed(() => {
  return isFailedStatus.value && props.message.canRetry !== false
})

// Methods
const handleRetry = async () => {
  if (retrying.value || !canRetry.value) return

  retrying.value = true
  try {
    await emit('retry', props.message.localId)
  } catch (error) {
    console.error('Retry failed:', error)
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
.message-user .message-content {
  margin-left: 30px;
}

.message-user {
  align-self: flex-end;
  margin-left: auto;
}

.message-user .message-content {
  background-color: var(--color-sent-message);
  color: var(--color-sent-text);
  border-bottom-right-radius: 5px;
}

.message-bot {
  align-self: flex-start;
}

.message-bot .message-content {
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
}



/* Failed status - red exclamation mark like WeChat */
.status-indicator.failed {
  cursor: pointer;
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

/* Responsive adjustments */
@media (max-width: 767px) {
  .message-bubble {
    max-width: 80%;
  }
}
</style> 