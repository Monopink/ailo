<template>
  <div class="modal-overlay" @click="handleOverlayClick">
    <div class="modal-content" @click.stop>
      <div class="modal-header">
        <h2>设置个人资料</h2>
        <p class="modal-subtitle">请完善您的基本信息以获得更好的体验</p>
      </div>

      <form @submit.prevent="handleSubmit" class="profile-form">
        <div class="form-group">
          <label for="nickname" class="form-label">
            昵称 <span class="required">*</span>
          </label>
          <input
            id="nickname"
            v-model="formData.nickname"
            type="text"
            class="form-input"
            :class="{ 'error': errors.nickname }"
            placeholder="请输入您的昵称"
            maxlength="50"
            required
          />
          <span v-if="errors.nickname" class="error-message">{{ errors.nickname }}</span>
        </div>

        <div class="form-group">
          <label for="gender" class="form-label">
            性别 <span class="required">*</span>
          </label>
          <select
            id="gender"
            v-model="formData.gender"
            class="form-select"
            :class="{ 'error': errors.gender }"
            required
          >
            <option value="">请选择性别</option>
            <option value="male">男</option>
            <option value="female">女</option>
            <option value="other">其他</option>
          </select>
          <span v-if="errors.gender" class="error-message">{{ errors.gender }}</span>
        </div>



        <div class="form-actions">
          <button
            type="submit"
            class="btn btn-primary"
            :disabled="isLoading || !isFormValid"
          >
            {{ isLoading ? '保存中...' : '完成设置' }}
          </button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useAuthStore } from '../stores/auth'

const emit = defineEmits(['close', 'success'])

const authStore = useAuthStore()

const isLoading = ref(false)
const formData = ref({
  nickname: '',
  gender: ''
})

const errors = ref({})

const isFormValid = computed(() => {
  return formData.value.nickname.trim() && formData.value.gender
})

const validateForm = () => {
  errors.value = {}
  
  if (!formData.value.nickname.trim()) {
    errors.value.nickname = '请输入昵称'
  } else if (formData.value.nickname.trim().length < 1) {
    errors.value.nickname = '昵称不能为空'
  } else if (formData.value.nickname.trim().length > 50) {
    errors.value.nickname = '昵称不能超过50个字符'
  }
  
  if (!formData.value.gender) {
    errors.value.gender = '请选择性别'
  }
  
  return Object.keys(errors.value).length === 0
}

const handleSubmit = async () => {
  if (!validateForm()) {
    return
  }

  isLoading.value = true

  try {
    await authStore.createProfile({
      nickname: formData.value.nickname.trim(),
      gender: formData.value.gender
    })

    emit('success')
    emit('close')
  } catch (error) {
    // Silent failure - no error display to user
    console.error('Profile setup failed:', error)
  } finally {
    isLoading.value = false
  }
}

const handleOverlayClick = () => {
  // Profile setup is required, so don't allow closing by clicking overlay
  // emit('close')
}
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: var(--color-bg-primary);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-xl);
  border: var(--border-width) solid var(--color-border);
  padding: var(--spacing-3xl);
  width: 90%;
  max-width: 400px;
  max-height: 80vh;
  overflow-y: auto;
}

.modal-header {
  text-align: center;
  margin-bottom: var(--spacing-3xl);
}

.modal-header h2 {
  color: var(--color-text-primary);
  margin: 0 0 var(--spacing-md) 0;
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
}

.modal-subtitle {
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
  margin: 0;
}

.profile-form {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-2xl);
}

.form-group {
  display: flex;
  flex-direction: column;
}

.form-label {
  color: var(--color-text-primary);
  font-weight: var(--font-weight-medium);
  margin-bottom: var(--spacing-md);
  font-size: var(--font-size-sm);
}

.required {
  color: var(--color-error);
}

.form-input,
.form-select {
  height: var(--input-height);
  padding: 0 var(--spacing-xl);
  border: var(--border-width) solid var(--color-border);
  border-radius: var(--radius-lg);
  background-color: var(--color-bg-primary);
  color: var(--color-text-primary);
  font-size: var(--font-size-sm);
  transition: border-color 0.2s ease;
  line-height: 1.4;
}

/* Prevent text shifting in select dropdown */
.form-select {
  appearance: none;
  background-image: url("data:image/svg+xml;charset=UTF-8,%3csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3e%3cpolyline points='6,9 12,15 18,9'%3e%3c/polyline%3e%3c/svg%3e");
  background-repeat: no-repeat;
  background-position: right var(--spacing-xl) center;
  background-size: 16px;
  padding-right: calc(var(--spacing-xl) * 2 + 16px);
}

.form-input:focus,
.form-select:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px rgba(66, 219, 90, 0.1);
}

.form-input.error,
.form-select.error {
  border-color: var(--color-error);
}

.error-message {
  color: var(--color-error);
  font-size: var(--font-size-xs);
  margin-top: var(--spacing-sm);
  min-height: 1.2em; /* Reserve space to prevent layout shift */
}

.form-actions {
  margin-top: var(--spacing-xl);
}

.btn {
  width: 100%;
  height: var(--button-height-lg);
  padding: 0 var(--spacing-3xl);
  border: none;
  border-radius: var(--radius-lg);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  cursor: pointer;
  transition: all 0.15s ease;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.btn-primary {
  background-color: var(--color-primary);
  color: white;
  box-shadow: var(--shadow-sm);
}

.btn-primary:hover:not(:disabled) {
  background-color: var(--color-primary-hover);
  color: white;
  box-shadow: var(--shadow-md);
}

.btn-primary:active:not(:disabled) {
  transform: scale(0.98);
  box-shadow: var(--shadow-xs);
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  transform: none;
}

/* Mobile optimizations */
@media (max-width: 767px) {
  .modal-content {
    width: 95%;
    max-height: 90vh;
    margin: var(--spacing-lg);
    padding: var(--spacing-2xl);
  }

  .modal-header {
    margin-bottom: var(--spacing-2xl);
  }

  .profile-form {
    gap: var(--spacing-xl);
  }
}


</style>
