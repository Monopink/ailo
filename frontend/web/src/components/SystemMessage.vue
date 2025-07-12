<template>
  <div
    class="system-message"
    role="status"
    aria-live="polite"
    :aria-label="`系统消息：${message}`">
    <span class="system-text" aria-hidden="true">{{ message }}</span>
    <span class="sr-only">系统消息：{{ message }}</span>
  </div>
</template>

<script setup>
import { uiLogger } from '../utils/logger.js'

const props = defineProps({
  message: {
    type: String,
    required: true
  }
})

// Log system message for debugging
uiLogger.debug('System message displayed', { message: props.message })
</script>

<style scoped>
.system-message {
  display: flex;
  justify-content: center;
  margin: 1rem 0;
  padding: 0 1rem;
}

.system-text {
  background-color: rgba(0, 0, 0, 0.05);
  color: var(--color-text-secondary);
  font-size: 0.75rem;
  padding: 0.25rem 0.75rem;
  border-radius: 12px;
  text-align: center;
  max-width: 80%;
  line-height: 1.4;
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

/* Dark mode support */
@media (prefers-color-scheme: dark) {
  .system-text {
    background-color: rgba(255, 255, 255, 0.1);
  }
}
</style>
