<template>
  <div class="settings-container">
    <div class="settings-header">
      <h1 class="settings-title">Settings</h1>
      <p class="settings-subtitle">Manage your preferences</p>
    </div>

    <div class="settings-content">
      <div class="settings-section">
        <h2 class="section-title">Account</h2>
        <div class="setting-item">
          <label class="setting-label">Username</label>
          <input type="text" class="input" v-model="userInfo.username" readonly />
        </div>
        
        <div class="setting-item">
          <label class="setting-label">Email</label>
          <input type="email" class="input" v-model="userInfo.email" readonly />
        </div>
        
        <div class="setting-item">
          <label class="setting-label">Last Login</label>
          <div class="setting-value">{{ formatDate(userInfo.last_login) }}</div>
        </div>
      </div>

      <div class="settings-section">
        <h2 class="section-title">Appearance</h2>
        <div class="setting-item">
          <label class="setting-label">Theme</label>
          <select class="select-input" v-model="theme" @change="updateTheme">
            <option value="light">Light</option>
            <option value="dark">Dark</option>
            <option value="auto">Auto</option>
          </select>
        </div>
      </div>

      <div class="settings-section">
        <h2 class="section-title">Security</h2>
        <div class="setting-item">
          <button class="btn btn-secondary" @click="changePassword">
            Change Password
          </button>
        </div>
        
        <div class="setting-item">
          <button class="btn btn-danger" @click="logout">
            Logout
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import themeManager from '@/utils/theme.js'

const router = useRouter()

const userInfo = ref({
  username: 'admin',
  email: 'admin@says.com',
  last_login: new Date()
})

// Use theme manager
const theme = themeManager.getTheme()
const setTheme = themeManager.setTheme.bind(themeManager)

function formatDate(date) {
  if (!date) return 'Never'
  return new Date(date).toLocaleString()
}

function updateTheme() {
  // Use the theme composable's setTheme method
  setTheme(theme.value)
}

function changePassword() {
  alert('Password change functionality will be implemented')
}

function logout() {
  if (confirm('Are you sure you want to logout?')) {
    localStorage.removeItem('admin_token')
    router.push('/login')
  }
}
</script>

<style scoped>
.settings-container {
  padding: var(--spacing-xl);
  max-width: 800px;
  margin: 0 auto;
}

.settings-header {
  margin-bottom: var(--spacing-2xl);
}

.settings-title {
  font-size: var(--font-size-3xl);
  font-weight: 600;
  color: var(--color-text-primary);
  margin: 0 0 var(--spacing-sm) 0;
}

.settings-subtitle {
  font-size: var(--font-size-lg);
  color: var(--color-text-secondary);
  margin: 0;
}

.settings-content {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-2xl);
}

.settings-section {
  background: var(--color-bg-primary);
  border: 1px solid var(--color-border-primary);
  border-radius: var(--radius-lg);
  padding: var(--spacing-xl);
}

.section-title {
  font-size: var(--font-size-xl);
  font-weight: 600;
  color: var(--color-text-primary);
  margin: 0 0 var(--spacing-lg) 0;
  padding-bottom: var(--spacing-sm);
  border-bottom: 1px solid var(--color-border-primary);
}

.setting-item {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
  margin-bottom: var(--spacing-lg);
}

.setting-item:last-child {
  margin-bottom: 0;
}

.setting-label {
  font-size: var(--font-size-sm);
  font-weight: 500;
  color: var(--color-text-secondary);
}

.setting-value {
  font-size: var(--font-size-base);
  color: var(--color-text-primary);
  padding: 2px 0;
}

.select-input {
  padding: 10px 12px;
  border: 1px solid var(--color-border-primary);
  border-radius: var(--radius-md);
  font-family: var(--font-family-base);
  font-size: var(--font-size-base);
  color: var(--color-text-primary);
  background-color: var(--color-bg-primary);
  transition: all var(--transition-fast);
  cursor: pointer;
}

.select-input:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px var(--color-primary-light);
}

.input {
  padding: 10px 12px;
  border: 1px solid var(--color-border-primary);
  border-radius: var(--radius-md);
  font-family: var(--font-family-base);
  font-size: var(--font-size-base);
  color: var(--color-text-primary);
  background-color: var(--color-bg-primary);
  transition: all var(--transition-fast);
}

.input:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px var(--color-primary-light);
}

.input:read-only {
  background-color: var(--color-bg-secondary);
  color: var(--color-text-tertiary);
}

.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 8px 16px;
  border: none;
  border-radius: var(--radius-md);
  font-family: var(--font-family-base);
  font-size: var(--font-size-sm);
  font-weight: 500;
  cursor: pointer;
  transition: all var(--transition-fast);
  min-height: 32px;
}

.btn-secondary {
  background-color: var(--color-bg-secondary);
  color: var(--color-text-primary);
  border: 1px solid var(--color-border-primary);
}

.btn-secondary:hover {
  background-color: var(--color-bg-tertiary);
}

.btn-danger {
  background-color: var(--color-error);
  color: var(--color-text-inverse);
}

.btn-danger:hover {
  background-color: #e6342a;
}

@media (max-width: 768px) {
  .settings-container {
    padding: var(--spacing-lg);
  }
  
  .settings-section {
    padding: var(--spacing-lg);
  }
}
</style>
