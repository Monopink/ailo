<template>
  <div class="message-failure-notice">
    <div class="notice-content">
      <span class="notice-text">{{ message }}</span>
    </div>
  </div>
</template>

<script setup>
defineProps({
  message: {
    type: String,
    required: true,
  },
});
</script>

<style scoped>
.message-failure-notice {
  display: flex;
  justify-content: center;
  margin: 1rem 0;
  padding: 0 1rem;
}

.notice-content {
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
}

.notice-text {
  color: var(--color-text-secondary);
  font-size: 0.75rem;
  line-height: 1.4;
}
</style>
