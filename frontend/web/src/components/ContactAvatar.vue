<template>
  <div 
    class="contact-avatar" 
    :class="sizeClass"
    :style="{ backgroundColor: avatarColor }"
  >
    <span class="avatar-text">{{ displayText }}</span>
  </div>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({
  nickname: {
    type: String,
    default: ''
  },
  size: {
    type: String,
    default: 'medium', // small, medium, large
    validator: (value) => ['small', 'medium', 'large'].includes(value)
  }
});

// Get first character of nickname for display
const displayText = computed(() => {
  return props.nickname?.charAt(0)?.toUpperCase() || '?';
});

// Size classes
const sizeClass = computed(() => {
  return `avatar-${props.size}`;
});

// Generate color based on nickname (placeholder for future algorithm)
// TODO: Implement proper color generation algorithm with brightness control
const avatarColor = computed(() => {
  if (!props.nickname) {
    return '#6b7280'; // Default gray color
  }
  
  // Placeholder: Simple hash-based color generation
  // This will be replaced with a proper algorithm later
  const colors = [
    '#ef4444', // red
    '#f97316', // orange  
    '#eab308', // yellow
    '#22c55e', // green
    '#06b6d4', // cyan
    '#3b82f6', // blue
    '#8b5cf6', // violet
    '#ec4899', // pink
  ];
  
  let hash = 0;
  for (let i = 0; i < props.nickname.length; i++) {
    hash = props.nickname.charCodeAt(i) + ((hash << 5) - hash);
  }
  
  return colors[Math.abs(hash) % colors.length];
});
</script>

<style scoped>
.contact-avatar {
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 500;
  color: white;
  flex-shrink: 0;
  user-select: none;
}

.avatar-text {
  font-size: inherit;
  line-height: 1;
}

/* Size variants */
.avatar-small {
  width: 32px;
  height: 32px;
  font-size: 0.75rem;
}

.avatar-medium {
  width: 40px;
  height: 40px;
  font-size: 0.875rem;
}

.avatar-large {
  width: 48px;
  height: 48px;
  font-size: 1rem;
}
</style>
