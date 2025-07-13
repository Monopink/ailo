<template>
  <div class="login-container">
    <div class="login-form">
      <div class="brand-header">
        <h1>{{ APP_CONFIG.BRAND_NAME }}</h1>
        <p class="brand-subtitle">重置密码</p>
      </div>

      <form @submit.prevent="handleResetPassword">
        <div class="form-group">
          <label for="phone">手机号</label>
          <div class="phone-input-group">
            <select v-model="countryCode" class="country-code-select">
              <option value="+86">+86</option>
            </select>
            <input
              type="tel"
              id="phone"
              v-model="phone"
              :class="{ 'error': showPhoneError && !isValidPhone }"
              @blur="showPhoneError = true"
              @input="showPhoneError = false"
              placeholder="请输入11位手机号"
              autocomplete="username"
              required
            />
          </div>
          <div class="error-message-container">
            <div v-if="showPhoneError && !isValidPhone" class="error-message">
              请输入有效的11位手机号码
            </div>
          </div>
        </div>

        <div class="form-group">
          <label for="code">验证码</label>
          <div class="code-group">
            <input
              type="text"
              id="code"
              v-model="code"
              :class="{ 'error': showCodeError && !code.trim() }"
              @blur="showCodeError = true"
              @input="showCodeError = false"
              placeholder="请输入验证码"
              maxlength="6"
              autocomplete="one-time-code"
              required
            />
            <button type="button" @click="handleSendCode" :disabled="isSendingCode || !isValidPhone" class="btn btn-secondary send-code-btn">
              {{ isSendingCode ? `${countdown}s` : '发送验证码' }}
            </button>
          </div>
          <div class="error-message-container">
            <div v-if="showCodeError && !code.trim()" class="error-message">
              请输入验证码
            </div>
          </div>
        </div>

        <div class="form-group">
          <label for="new-password">新密码</label>
          <div class="password-input-group">
            <input
              :type="showPassword ? 'text' : 'password'"
              id="new-password"
              v-model="newPassword"
              :class="{ 'error': showPasswordError && !isValidPassword }"
              @blur="showPasswordError = true"
              @input="showPasswordError = false"
              placeholder="请输入至少8位新密码"
              autocomplete="new-password"
              required
            />
            <button
              type="button"
              @click="showPassword = !showPassword"
              class="password-toggle"
              :aria-label="showPassword ? '隐藏密码' : '显示密码'"
            >
              {{ showPassword ? '🙉' : '🙈' }}
            </button>
          </div>
          <div class="error-message-container">
            <div v-if="showPasswordError && !isValidPassword" class="error-message">
              密码至少需要8位字符
            </div>
          </div>
        </div>

        <button type="submit" :disabled="isLoading || !isFormValid" class="btn btn-primary submit-btn">
          {{ isLoading ? '重置中...' : '重置密码' }}
        </button>
      </form>

      <p class="switch-form">
        想起密码了？ <router-link to="/login" class="text-accent">返回登录</router-link>
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue';
import { useRouter } from 'vue-router';
import { useToast } from 'vue-toastification';
import { apiClient } from '../utils/apiHelpers';
import { APP_CONFIG } from '../config/constants';

const router = useRouter();
const toast = useToast();

const phone = ref('');
const code = ref('');
const newPassword = ref('');
const countryCode = ref('+86');
const showPassword = ref(false);
const isLoading = ref(false);

const isSendingCode = ref(false);
const countdown = ref(60);

// Validation states
const showPhoneError = ref(false);
const showCodeError = ref(false);
const showPasswordError = ref(false);

// Computed validation
const isValidPhone = computed(() => {
  return /^1[3-9]\d{9}$/.test(phone.value);
});

const isValidPassword = computed(() => {
  return newPassword.value.length >= 8;
});

const isFormValid = computed(() => {
  return isValidPhone.value && code.value.trim() && isValidPassword.value;
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

const handleResetPassword = async () => {
  isLoading.value = true;
  try {
    await apiClient.post('/auth/reset-password', {
      phone: phone.value,
      code: code.value,
      new_password: newPassword.value,
    });
    toast.success('密码重置成功！请使用新密码登录。');
    router.push('/login');
  } catch (err) {
    const errorMessage = err.response?.data?.detail || '密码重置失败，请检查验证码是否正确。';
    toast.error(errorMessage);
  } finally {
    isLoading.value = false;
  }
};
</script>

<style scoped>
.login-container {
  width: 100%;
  height: 100vh;
  display: flex;
  justify-content: center;
  align-items: center;
  padding: var(--spacing-3xl);
  background: var(--color-bg-primary);
  overflow: hidden;
}

.login-form {
  width: 100%;
  max-width: 320px;
  padding: 0;
}

.brand-header {
  text-align: center;
  margin-bottom: var(--spacing-5xl);
}

.brand-header h1 {
  margin: 0 0 var(--spacing-sm) 0;
  color: var(--color-text-primary);
  font-weight: var(--font-weight-semibold);
  font-size: 28px;
  letter-spacing: -0.5px;
}

.brand-subtitle {
  margin: 0;
  color: var(--color-text-secondary);
  font-size: var(--font-size-md);
  font-weight: var(--font-weight-normal);
}

form {
  margin-bottom: var(--spacing-2xl);
}

.form-group {
  margin-bottom: var(--spacing-2xl);
}

.form-group label {
  display: block;
  margin-bottom: var(--spacing-md);
  color: var(--color-text-primary);
  font-weight: var(--font-weight-medium);
  font-size: var(--font-size-sm);
}

.form-group input {
  width: 100%;
  padding: var(--spacing-lg) var(--spacing-xl);
  border: var(--border-width) solid var(--color-border);
  background-color: var(--color-bg-primary);
  color: var(--color-text-primary);
  border-radius: var(--radius-md);
  font-size: var(--font-size-base);
  line-height: 1.5;
  height: 40px;
  transition: all 0.2s ease;
  box-shadow: var(--shadow-xs);
}

.form-group input:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px var(--color-primary-subtle);
}

.form-group input.error {
  border-color: var(--color-error);
  box-shadow: 0 0 0 3px var(--color-error-subtle);
}

/* Error message container to prevent layout shift */
.error-message-container {
  min-height: 16px; /* Reserve minimal space for error messages */
  margin-top: var(--spacing-xs);
}

.error-message {
  color: var(--color-error);
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-medium);
  line-height: 1.3;
}

.phone-input-group {
  display: flex;
  gap: var(--spacing-sm);
}

.country-code-select {
  flex-shrink: 0;
  width: 80px;
  padding: 0 var(--spacing-sm);
  border: var(--border-width) solid var(--color-border);
  background-color: var(--color-bg-primary);
  color: var(--color-text-primary);
  border-radius: var(--radius-md);
  font-size: var(--font-size-sm);
  height: 40px;
  line-height: 40px; /* Match height for vertical centering */
  transition: all 0.2s ease;
  box-shadow: var(--shadow-xs);
  appearance: none;
  text-align: center;
}

.country-code-select:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px var(--color-primary-subtle);
}

.phone-input-group input {
  flex: 1;
}

.password-input-group {
  position: relative;
  display: flex;
  align-items: center;
}

.password-input-group input {
  flex: 1;
  padding-right: 40px;
}

.password-toggle {
  position: absolute;
  right: var(--spacing-lg);
  background: none;
  border: none;
  cursor: pointer;
  font-size: 16px;
  color: var(--color-text-secondary);
  transition: color 0.2s ease;
  padding: 0;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.password-toggle:hover {
  color: var(--color-text-primary);
}

.code-group {
  display: flex;
  align-items: stretch;
  gap: var(--spacing-lg);
}

.code-group input {
  flex: 1;
}

.send-code-btn {
  flex-shrink: 0;
  min-width: 90px;
  height: 40px;
  padding: 0 var(--spacing-lg);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  white-space: nowrap;
}

.submit-btn {
  width: 100%;
  height: 40px;
  padding: 0 var(--spacing-xl);
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-medium);
  margin-top: var(--spacing-xl);
  border-radius: var(--radius-md);
}

.submit-btn:disabled,
.send-code-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.switch-form {
  text-align: center;
  margin-top: var(--spacing-4xl);
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
}

.switch-form a {
  text-decoration: none;
  color: var(--color-primary);
  font-weight: var(--font-weight-medium);
  transition: color 0.2s ease;
}

.switch-form a:hover {
  color: var(--color-primary-hover);
}

/* Responsive adjustments */
@media (max-width: 767px) {
  .login-container {
    padding: var(--spacing-2xl);
  }

  .login-form {
    max-width: 100%;
  }

  .brand-header h1 {
    font-size: 24px;
  }
}
</style>
