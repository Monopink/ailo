<template>
  <div class="layout-container">
    <aside class="sidebar">
      <div class="sidebar-header">
        <div class="user-info">
          <span class="user-name">{{ currentUser?.username || 'Admin User' }}</span>
          <span class="user-role">{{ getRoleDisplay(currentUser?.role) }}</span>
        </div>
      </div>

      <nav class="sidebar-nav">
        <router-link to="/dashboard" class="nav-item" :class="{ 'nav-item-active': $route.path === '/dashboard' }" draggable="false">
          <span class="nav-icon">📊</span>
          <span class="nav-text">Dashboard</span>
        </router-link>

        <!-- Business Management will be added in Phase 4 -->

        <!-- Admin Management -->
        <router-link to="/system/users" class="nav-item" :class="{ 'nav-item-active': $route.path === '/system/users' }" draggable="false">
          <span class="nav-icon">👤</span>
          <span class="nav-text">Admin Users</span>
        </router-link>

        <!-- Development Tools -->
        <div class="nav-separator"></div>
        <router-link to="/components" class="nav-item" :class="{ 'nav-item-active': $route.path === '/components' }" draggable="false">
          <span class="nav-icon">🎨</span>
          <span class="nav-text">Components</span>
        </router-link>

        <!-- Settings -->
        <div class="nav-separator"></div>
        <router-link to="/settings" class="nav-item" :class="{ 'nav-item-active': $route.path === '/settings' }" draggable="false">
          <span class="nav-icon">⚙️</span>
          <span class="nav-text">Settings</span>
        </router-link>
      </nav>


    </aside>

    <main class="main-content">
      <section class="content-area">
        <router-view />
      </section>
    </main>
  </div>
</template>

<script setup>
// Simple layout component for admin panel
import { computed } from 'vue'
import { useAuthStore } from '@/store'

const authStore = useAuthStore()
const currentUser = computed(() => authStore.user)

// Role display mapping
const getRoleDisplay = (role) => {
  const roleMap = {
    'super_admin': 'Super Admin',
    'admin': 'Admin',
    'viewer': 'Viewer'
  }
  return roleMap[role] || 'Admin User'
}
</script>

<style scoped>
.layout-container {
  display: flex;
  width: 100%;
  height: 100vh;
  background-color: var(--color-bg-primary);
}

.sidebar {
  width: 260px;
  background-color: var(--color-bg-secondary);
  border-right: 1px solid var(--color-border-primary);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}

/* Improve sidebar visibility in light mode */
.sidebar {
  box-shadow: 1px 0 3px rgba(0, 0, 0, 0.1);
}

.sidebar-header {
  padding: var(--spacing-lg) var(--spacing-lg);
  border-bottom: 1px solid var(--color-border-primary);
}

.user-info {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.user-name {
  font-size: var(--font-size-base);
  font-weight: 600;
  color: var(--color-text-primary);
}

.user-role {
  font-size: var(--font-size-sm);
  font-weight: 400;
  color: var(--color-text-secondary);
}

.sidebar-nav {
  flex: 1;
  padding: var(--spacing-lg) var(--spacing-sm);
}

.nav-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  padding: 10px 16px;
  color: var(--color-text-secondary);
  text-decoration: none;
  transition: all var(--transition-fast);
  border-radius: var(--radius-sm);
  margin-bottom: 4px;
  user-select: text;
  -webkit-user-drag: none;
  -khtml-user-drag: none;
  -moz-user-drag: none;
  -o-user-drag: none;
}

.nav-item:hover {
  background-color: var(--color-bg-tertiary);
  color: var(--color-text-primary);
}

.nav-item-active {
  background-color: var(--color-primary-light);
  color: var(--color-primary);
}

.nav-icon {
  font-size: 16px;
  width: 18px;
  text-align: center;
  flex-shrink: 0;
}

.nav-text {
  font-size: var(--font-size-base);
  font-weight: 500;
  flex: 1;
}

/* Tree menu styles */
.nav-group {
  margin-bottom: 4px;
}

.nav-group-header {
  cursor: pointer;
}

.nav-arrow {
  font-size: 10px;
  color: var(--color-text-tertiary);
  margin-left: auto;
}

.nav-arrow-open {
  transform: rotate(180deg);
}

.nav-submenu {
  margin-top: 2px;
}

.nav-subitem {
  padding-left: 48px;
  font-size: var(--font-size-xs);
  margin-bottom: 2px;
}

.nav-subitem .nav-icon {
  font-size: 14px;
  width: 16px;
}

.nav-subitem .nav-text {
  font-size: var(--font-size-base);
  font-weight: 400;
}

.nav-separator {
  height: 1px;
  background-color: var(--color-border-primary);
  margin: var(--spacing-md) var(--spacing-md);
}

.main-content {
  display: flex;
  flex-direction: column;
  flex: 1;
  overflow: hidden;
}

.content-area {
  flex: 1;
  overflow: auto;
  background-color: var(--color-bg-primary);
  padding-top: var(--spacing-lg);
}

@media (max-width: 768px) {
  .sidebar {
    width: 200px;
  }

  .nav-text {
    display: none;
  }

  .sidebar-title {
    font-size: var(--font-size-lg);
  }
}
</style>
