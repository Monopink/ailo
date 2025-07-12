<template>
  <button
    @click="toggleTheme"
    class="theme-toggle-btn"
    type="button"
    :title="isDarkMode ? '切换至亮色模式' : '切换至暗色模式'"
    :aria-label="`当前主题：${isDarkMode ? '暗色' : '亮色'}模式，点击切换至${isDarkMode ? '亮色' : '暗色'}模式`"
    :aria-pressed="isDarkMode"
  >
    <!-- Sun icon for dark mode (to switch to light) -->
    <svg
      v-if="isDarkMode"
      xmlns="http://www.w3.org/2000/svg"
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
      aria-hidden="true">
      <circle cx="12" cy="12" r="5"></circle>
      <line x1="12" y1="1" x2="12" y2="3"></line>
      <line x1="12" y1="21" x2="12" y2="23"></line>
      <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line>
      <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line>
      <line x1="1" y1="12" x2="3" y2="12"></line>
      <line x1="21" y1="12" x2="23" y2="12"></line>
      <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line>
      <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>
    </svg>

    <!-- Moon icon for light mode (to switch to dark) -->
    <svg
      v-else
      xmlns="http://www.w3.org/2000/svg"
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
      aria-hidden="true">
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
    </svg>

    <span class="sr-only">
      {{ isDarkMode ? '切换至亮色模式' : '切换至暗色模式' }}
    </span>
  </button>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { uiLogger } from '../utils/logger.js'

const isDarkMode = ref(false)

onMounted(() => {
  // Get the current theme
  const currentTheme = document.documentElement.getAttribute('data-theme')
  isDarkMode.value = currentTheme === 'dark'

  uiLogger.debug('ThemeToggle initialized', {
    currentTheme,
    isDarkMode: isDarkMode.value
  })
})

const toggleTheme = () => {
  // Toggle theme
  isDarkMode.value = !isDarkMode.value

  const newTheme = isDarkMode.value ? 'dark' : 'light'

  // Update document theme attribute
  document.documentElement.setAttribute('data-theme', newTheme)

  // Save preference to local storage
  try {
    localStorage.setItem('theme', newTheme)
    uiLogger.info('Theme toggled successfully', {
      newTheme,
      isDarkMode: isDarkMode.value
    })
  } catch (error) {
    uiLogger.error('Failed to save theme preference', error)
  }
}
</script>

<style scoped>
.theme-toggle-btn {
  background: var(--accent-color-light);
  border: none;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-color);
  transition: background-color 0.3s, transform 0.2s, box-shadow 0.2s;
  box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
}

.theme-toggle-btn:hover {
  background: var(--accent-color);
  transform: scale(1.05);
}

.theme-toggle-btn:focus {
  outline: none;
}

.theme-toggle-btn:active {
  transform: scale(0.95);
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
</style> 