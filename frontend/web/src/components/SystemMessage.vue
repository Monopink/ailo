<template>
  <div class="system-message">
    <span class="system-text">{{ message }}</span>
  </div>
</template>

<script>
export default {
  name: 'SystemMessage',
  props: {
    message: {
      type: String,
      required: true
    }
  }
}
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

/* Dark mode support */
@media (prefers-color-scheme: dark) {
  .system-text {
    background-color: rgba(255, 255, 255, 0.1);
  }
}
</style>
