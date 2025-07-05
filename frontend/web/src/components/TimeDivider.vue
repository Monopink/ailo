<template>
  <div class="time-divider">
    <span class="time-text">{{ formattedTime }}</span>
  </div>
</template>

<script>
export default {
  name: 'TimeDivider',
  props: {
    timestamp: {
      type: [String, Date],
      required: true
    }
  },
  computed: {
    formattedTime() {
      const date = new Date(this.timestamp)
      const now = new Date()
      const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
      const messageDate = new Date(date.getFullYear(), date.getMonth(), date.getDate())
      
      // Check if it's today
      if (messageDate.getTime() === today.getTime()) {
        return date.toLocaleTimeString('zh-CN', { 
          hour: '2-digit', 
          minute: '2-digit',
          hour12: false 
        })
      }
      
      // Check if it's yesterday
      const yesterday = new Date(today)
      yesterday.setDate(yesterday.getDate() - 1)
      if (messageDate.getTime() === yesterday.getTime()) {
        return '昨天 ' + date.toLocaleTimeString('zh-CN', { 
          hour: '2-digit', 
          minute: '2-digit',
          hour12: false 
        })
      }
      
      // Check if it's this year
      if (date.getFullYear() === now.getFullYear()) {
        return date.toLocaleDateString('zh-CN', { 
          month: 'long', 
          day: 'numeric' 
        }) + ' ' + date.toLocaleTimeString('zh-CN', { 
          hour: '2-digit', 
          minute: '2-digit',
          hour12: false 
        })
      }
      
      // Different year
      return date.toLocaleDateString('zh-CN', { 
        year: 'numeric',
        month: 'long', 
        day: 'numeric' 
      }) + ' ' + date.toLocaleTimeString('zh-CN', { 
        hour: '2-digit', 
        minute: '2-digit',
        hour12: false 
      })
    }
  }
}
</script>

<style scoped>
.time-divider {
  display: flex;
  justify-content: center;
  margin: 1rem 0;
  padding: 0 1rem;
}

.time-text {
  background-color: rgba(0, 0, 0, 0.05);
  color: var(--color-text-secondary);
  font-size: 0.75rem;
  padding: 0.25rem 0.75rem;
  border-radius: 12px;
  text-align: center;
  line-height: 1.4;
}

/* Dark mode support */
@media (prefers-color-scheme: dark) {
  .time-text {
    background-color: rgba(255, 255, 255, 0.1);
  }
}
</style>
