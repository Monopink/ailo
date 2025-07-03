<template>
  <div class="register-container grid-bg">
    <div class="register-form glass-panel">
      <h1>注册账户</h1>
      <form @submit.prevent="handleRegister">
        <div class="form-group">
          <label for="phone">手机号</label>
          <input type="tel" id="phone" v-model="phone" required placeholder="请输入您的手机号" />
        </div>
        <div class="form-group">
          <label for="code">验证码</label>
          <div class="code-group">
            <input type="text" id="code" v-model="code" required placeholder="请输入6位验证码" />
            <button type="button" @click="handleSendCode" :disabled="isSendingCode" class="btn">
              {{ isSendingCode ? `${countdown}s后重新发送` : '发送验证码' }}
            </button>
          </div>
        </div>
        <div class="form-group">
          <label for="password">密码</label>
          <input type="password" id="password" v-model="password" required placeholder="请输入至少8位密码" />
        </div>
        <button type="submit" :disabled="isLoading" class="btn btn-primary">
          {{ isLoading ? '注册中...' : '注册' }}
        </button>
      </form>
      <p class="switch-form">
        已有账户？ <router-link to="/login" class="text-accent">立即登录</router-link>
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { useToast } from 'vue-toastification';
import apiClient from '../services/api';

const phone = ref('');
const code = ref('');
const password = ref('');
const router = useRouter();
const toast = useToast();

const isSendingCode = ref(false);
const countdown = ref(60);
const isLoading = ref(false);

const handleSendCode = async () => {
  if (!phone.value) {
    toast.error('请输入手机号码。');
    return;
  }
  // Basic phone validation
  if (!/^1[3-9]\d{9}$/.test(phone.value)) {
    toast.error('请输入有效的11位手机号码。');
    return;
  }

  isSendingCode.value = true;
  countdown.value = 60;

  try {
    await apiClient.post('/auth/send-code', { phone: phone.value });
    toast.success('验证码已发送！');
    // Start countdown
    const interval = setInterval(() => {
      countdown.value--;
      if (countdown.value <= 0) {
        clearInterval(interval);
        isSendingCode.value = false;
        countdown.value = 60;
      }
    }, 1000);
  } catch (err) {
    const errorMessage = err.response?.data?.detail || '发送验证码失败，请稍后重试。';
    toast.error(errorMessage);
    isSendingCode.value = false;
  }
};

const handleRegister = async () => {
  isLoading.value = true;
  try {
    const response = await apiClient.post('/auth/register', {
      phone: phone.value,
      code: code.value,
      password: password.value,
    });

    if (response.status === 200 || response.status === 201) {
      toast.success('注册成功！请登录。');
      router.push('/login');
    }
  } catch (err) {
    const errorMessage = err.response?.data?.detail || '注册失败，请检查您的输入。';
    toast.error(errorMessage);
    console.error('Registration failed:', err);
  } finally {
    isLoading.value = false;
  }
};
</script>

<style scoped>
.register-container {
  width: 100%;
  min-height: 100vh;
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 2rem;
}

.register-form {
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

button[type="button"] {
  padding: 0.75rem 0.5rem;
  white-space: nowrap;
}

button[type="button"]:disabled,
button[type="submit"]:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

button[type="submit"] {
  width: 100%;
  padding: 0.75rem;
  font-size: 1rem;
  margin-top: 1rem;
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
  .register-container {
    padding: 1rem;
  }

  .register-form {
    padding: 1.5rem 1rem;
  }
}
</style> 