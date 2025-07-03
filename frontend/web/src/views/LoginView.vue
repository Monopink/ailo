<template>
  <div class="login-container grid-bg">
    <div class="login-form glass-panel">
      <h1>登录</h1>
      <div class="login-tabs">
        <button :class="{ 'active': loginMethod === 'password', 'tab-btn': true }" @click="loginMethod = 'password'">
          密码登录
        </button>
        <button :class="{ 'active': loginMethod === 'code', 'tab-btn': true }" @click="loginMethod = 'code'">
          验证码登录
        </button>
      </div>

      <!-- Password Login Form -->
      <form v-if="loginMethod === 'password'" @submit.prevent="handlePasswordLogin" key="password-form">
        <div class="form-group">
          <label for="phone-pass">手机号</label>
          <input type="tel" id="phone-pass" v-model="phone" required />
        </div>
        <div class="form-group">
          <label for="password">密码</label>
          <input type="password" id="password" v-model="password" required />
        </div>
        <button type="submit" :disabled="isLoading" class="btn btn-primary">
          {{ isLoading ? '登录中...' : '登录' }}
        </button>
      </form>

      <!-- Code Login Form -->
      <form v-if="loginMethod === 'code'" @submit.prevent="handleCodeLogin" key="code-form">
        <div class="form-group">
          <label for="phone-code">手机号</label>
          <input type="tel" id="phone-code" v-model="phone" required />
        </div>
        <div class="form-group">
          <label for="code">验证码</label>
          <div class="code-group">
            <input type="text" id="code" v-model="code" required />
            <button type="button" @click="handleSendCode" :disabled="isSendingCode" class="btn">
              {{ isSendingCode ? `${countdown}s` : '发送验证码' }}
            </button>
          </div>
        </div>
        <button type="submit" :disabled="isLoading" class="btn btn-primary">
          {{ isLoading ? '登录中...' : '登录' }}
        </button>
      </form>

      <p class="switch-form">
        还没有账户？ <router-link to="/register" class="text-accent">立即注册</router-link>
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useToast } from 'vue-toastification';
import apiClient from '../services/api';
import { useAuthStore } from '../stores/auth';

const router = useRouter();
const authStore = useAuthStore();
const toast = useToast();

const loginMethod = ref('password'); // 'password' or 'code'
const phone = ref('');
const password = ref('');
const code = ref('');
const isLoading = ref(false);

const isSendingCode = ref(false);
const countdown = ref(60);

// Reset fields when switching login method
watch(loginMethod, () => {
  phone.value = '';
  password.value = '';
  code.value = '';
});

const handleSendCode = async () => {
  if (!phone.value || !/^1[3-9]\d{9}$/.test(phone.value)) {
    toast.error('请输入有效的11位手机号码。');
    return;
  }
  isSendingCode.value = true;
  countdown.value = 60;
  try {
    await apiClient.post('/auth/send-code', { phone: phone.value });
    toast.success('验证码已发送！');
    const interval = setInterval(() => {
      countdown.value--;
      if (countdown.value <= 0) {
        clearInterval(interval);
        isSendingCode.value = false;
      }
    }, 1000);
  } catch (err) {
    const errorMessage = err.response?.data?.detail || '发送验证码失败。';
    toast.error(errorMessage);
    isSendingCode.value = false;
  }
};

const handlePasswordLogin = async () => {
  isLoading.value = true;
  try {
    await authStore.loginWithPassword(phone.value, password.value);
    router.push('/');
  } catch (err) {
    // Error is already handled by the auth store, which shows a toast.
    // We just need to catch it to prevent unhandled promise rejection warnings.
    console.error("Login failed:", err);
  } finally {
    isLoading.value = false;
  }
};

const handleCodeLogin = async () => {
  isLoading.value = true;
  try {
    const response = await apiClient.post('/auth/login/code', {
      phone: phone.value,
      code: code.value,
    });
    await authStore.login(response.data.access_token);
    router.push('/');
  } catch (err) {
    const errorMessage = err.response?.data?.detail || '验证码错误或已过期。';
    toast.error(errorMessage);
  } finally {
    isLoading.value = false;
  }
};
</script>

<style scoped>
.login-container {
  width: 100%;
  min-height: 100vh;
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 2rem;
}

.login-form {
  width: 100%;
  max-width: 400px;
  padding: 2rem;
  background: var(--color-bg-overlay);
}

h1 {
  text-align: center;
  margin-bottom: 1.5rem;
  color: var(--color-text-primary);
  font-weight: 500;
}

.login-tabs {
  display: flex;
  margin-bottom: 1.5rem;
  border-radius: var(--border-radius-sm);
  overflow: hidden;
  border: var(--border-width) solid var(--color-border);
}

.tab-btn {
  flex-grow: 1;
  padding: 0.75rem;
  border: none;
  background: var(--color-bg-primary);
  cursor: pointer;
  font-size: 0.95rem;
  color: var(--color-text-secondary);
  border-right: var(--border-width) solid var(--color-border);
}

.tab-btn:last-child {
  border-right: none;
}

.tab-btn.active {
  color: var(--color-text-primary);
  font-weight: 500;
  background-color: var(--color-accent-soft);
}

form {
  padding: 1.5rem 0;
  margin-bottom: 1rem;
}

.form-group {
  margin-bottom: 1.5rem;
}

.form-group label {
  display: block;
  margin-bottom: 0.5rem;
  color: var(--color-text-primary);
  font-weight: 500;
}

.form-group input {
  width: 100%;
  padding: 0.75rem;
  border: var(--border-width) solid var(--color-border);
  background-color: var(--color-bg-primary);
  color: var(--color-text-primary);
  border-radius: var(--border-radius-sm);
}

.code-group {
  display: flex;
  align-items: center;
}

.code-group input {
  flex-grow: 1;
  margin-right: 0.5rem;
}

button[type="submit"] {
  width: 100%;
  padding: 0.75rem;
  font-size: 1rem;
  margin-top: 1rem;
}

button[type="submit"]:disabled,
button[type="button"]:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.switch-form {
  text-align: center;
  margin-top: 1rem;
  color: var(--color-text-secondary);
}

.switch-form a {
  text-decoration: none;
}

/* Responsive adjustments */
@media (max-width: 767px) {
  .login-container {
    padding: 1rem;
  }

  .login-form {
    padding: 1.5rem 1rem;
  }
}
</style>