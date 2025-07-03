<template>
  <div class="message-bubble" :class="`message-${message.sender}`">
    <div class="message-content">
      <p>{{ message.text }}</p>
    </div>
  </div>
</template>

<script setup>
defineProps({
  message: {
    type: Object,
    required: true,
  },
});
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
}

.message-user {
  align-self: flex-end;
  margin-left: auto;
}

.message-user .message-content {
  background-color: var(--color-user-message);
  color: var(--color-user-text);
  border-bottom-right-radius: 5px;
}

.message-bot {
  align-self: flex-start;
}

.message-bot .message-content {
  background-color: var(--color-bot-message);
  color: var(--color-bot-text);
  border-bottom-left-radius: 5px;
}

.message-content p {
  margin: 0;
  white-space: pre-wrap; /* Preserve line breaks */
}

/* Responsive adjustments */
@media (max-width: 767px) {
  .message-bubble {
    max-width: 80%;
  }
}
</style> 