<template>
  <div class="login-container">
    <div class="login-card">
      <div class="login-content">
        <div class="login-header">
          <h1 class="login-title">Login</h1>
        </div>

        <form class="login-form" @submit.prevent="handleLogin">
          <div class="form-group">
            <input
              v-model="loginInfo.username"
              type="text"
              class="form-input"
              placeholder="Username"
              :maxlength="20"
              autofocus
              required
            />
          </div>

          <div class="form-group">
            <input
              v-model="loginInfo.password"
              type="password"
              class="form-input"
              placeholder="Password"
              :maxlength="20"
              required
              @keypress.enter="handleLogin"
            />
          </div>

          <button
            type="submit"
            class="btn btn-primary login-button"
            :disabled="loading"
          >
            <span v-if="loading">Signing in...</span>
            <span v-else>Sign In</span>
          </button>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/store'
import api from '@/api'

const router = useRouter()
const authStore = useAuthStore()

const loginInfo = ref({
  username: '',
  password: '',
})

const loading = ref(false)

async function handleLogin() {
  const { username, password } = loginInfo.value
  if (!username || !password) {
    alert('Please enter username and password')
    return
  }

  try {
    loading.value = true

    // Login request
    const response = await api.login({ username, password })

    if (response.code === 200 && response.data && response.data.access_token) {
      // Store token
      authStore.setToken(response.data.access_token)

      // Get user info
      try {
        const userResponse = await api.getUserInfo()
        if (userResponse.code === 200 && userResponse.data) {
          authStore.setUser(userResponse.data)
        }
      } catch (userError) {
        console.warn('Failed to get user info:', userError)
        // Continue anyway, user info can be loaded later
      }

      router.push('/dashboard')
    } else {
      console.log('Response data:', response)
      alert('Login failed: Invalid response format')
    }
  } catch (error) {
    console.error('Login error:', error)
    if (error.response && error.response.data && error.response.data.detail) {
      alert(`Login failed: ${error.response.data.detail}`)
    } else {
      alert('Login failed. Please check your credentials.')
    }
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-container {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background-color: var(--color-bg-primary);
  padding: var(--spacing-md);
}

.login-header {
  text-align: center;
  margin-bottom: var(--spacing-xl);
}

.login-title {
  font-size: var(--font-size-2xl);
  font-weight: 600;
  color: var(--color-text-primary);
  margin: 0 0 var(--spacing-sm) 0;
}

.login-subtitle {
  font-size: var(--font-size-base);
  color: var(--color-text-secondary);
  margin: 0;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-lg);
  width: 280px;
  margin: 0 auto;
  padding: 0;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.form-label {
  font-size: var(--font-size-sm);
  font-weight: 500;
  color: var(--color-text-secondary);
}

.form-input {
  width: 100%;
  padding: 12px 16px;
  border: 1px solid var(--color-border-primary);
  border-radius: var(--radius-sm);
  font-size: var(--font-size-base);
  color: var(--color-text-primary);
  background-color: var(--color-bg-secondary);
  transition: all var(--transition-fast);
  min-height: 44px;
  box-sizing: border-box;
}

.form-input:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px var(--color-primary-light);
}

.login-button {
  width: 100%;
  padding: 12px 32px;
  font-size: var(--font-size-base);
  font-weight: 500;
  background-color: var(--color-primary);
  color: var(--color-text-inverse);
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--transition-fast);
  min-height: 44px;
}

.login-button:hover {
  background-color: var(--color-primary-hover);
}

.login-button:active {
  background-color: var(--color-primary-pressed);
  opacity: 0.9;
}

.login-button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* Responsive design */
@media (max-width: 320px) {
  .login-container {
    padding: var(--spacing-sm);
  }

  .login-form {
    width: 100%;
    max-width: 280px;
    padding: 0 var(--spacing-md);
  }
}
</style>
