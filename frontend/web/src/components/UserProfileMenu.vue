<template>
  <div class="user-profile-menu" ref="menuContainer">
    <div class="nickname-display" @click="toggleMenu">
      {{ authStore.user?.nickname || '点击设置昵称' }}
    </div>
    
    <div v-if="showMenu" class="dropdown-menu" @click.stop>
      <button @click="handleEditProfile" class="menu-item">
        编辑资料
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useAuthStore } from '../stores/auth'

const emit = defineEmits(['edit-profile'])

const authStore = useAuthStore()
const showMenu = ref(false)
const menuContainer = ref(null)

const toggleMenu = () => {
  showMenu.value = !showMenu.value
}

const handleEditProfile = () => {
  showMenu.value = false
  emit('edit-profile')
}

const handleClickOutside = (event) => {
  if (menuContainer.value && !menuContainer.value.contains(event.target)) {
    showMenu.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})
</script>

<style scoped>
.user-profile-menu {
  position: relative;
  display: inline-block;
}

.nickname-display {
  cursor: pointer;
  padding: 0.5rem;
  border-radius: var(--border-radius-sm);
  transition: background-color 0.2s;
  color: var(--color-text-primary);
  user-select: none;
}

.nickname-display:hover {
  background-color: var(--color-bg-secondary);
}

.dropdown-menu {
  position: absolute;
  top: 100%;
  left: 0;
  background: var(--color-bg-primary);
  border: var(--border-width) solid var(--color-border);
  border-radius: var(--border-radius-sm);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  min-width: 120px;
  z-index: 1000;
  margin-top: 0.25rem;
}

.menu-item {
  display: block;
  width: 100%;
  padding: 0.75rem 1rem;
  background: none;
  border: none;
  text-align: left;
  color: var(--color-text-primary);
  cursor: pointer;
  font-size: 0.9rem;
  transition: background-color 0.2s;
}

.menu-item:hover {
  background-color: var(--color-bg-secondary);
}

.menu-item:first-child {
  border-radius: var(--border-radius-sm) var(--border-radius-sm) 0 0;
}

.menu-item:last-child {
  border-radius: 0 0 var(--border-radius-sm) var(--border-radius-sm);
}
</style>
