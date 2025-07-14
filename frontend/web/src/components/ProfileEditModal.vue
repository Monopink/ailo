<template>
  <div class="modal-overlay" @click="handleOverlayClick">
    <div class="modal-content" @click.stop>
      <div class="modal-header">
        <h2>编辑资料</h2>
        <button @click="$emit('close')" class="close-btn">×</button>
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
            type="button"
            @click="$emit('close')"
            class="btn btn-secondary"
            :disabled="isLoading"
          >
            取消
          </button>
          <button
            type="submit"
            class="btn btn-primary"
            :disabled="isLoading || !isFormValid"
          >
            {{ isLoading ? '保存中...' : '保存' }}
          </button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
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

onMounted(() => {
  // Pre-fill form with current user data
  if (authStore.user) {
    formData.value.nickname = authStore.user.nickname || ''
    formData.value.gender = authStore.user.gender || ''
  }
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
    await authStore.updateProfile({
      nickname: formData.value.nickname.trim(),
      gender: formData.value.gender
    })

    emit('success')
    emit('close')
  } catch (error) {
    // Silent failure - no error display to user
    console.error('Profile update failed:', error)
  } finally {
    isLoading.value = false
  }
}

const handleOverlayClick = () => {
  emit('close')
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
  padding: var(--spacing-3xl);
  width: 90%;
  max-width: 400px;
  box-shadow: var(--shadow-xl);
  border: var(--border-width) solid var(--color-border);
  position: relative;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}

.modal-header h2 {
  color: var(--color-text-primary);
  margin: 0;
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
}

.close-btn {
  background: none;
  border: none;
  font-size: 1.5rem;
  color: var(--color-text-secondary);
  cursor: pointer;
  padding: 0;
  width: 2rem;
  height: 2rem;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  transition: background-color 0.2s;
}

.close-btn:hover {
  background-color: var(--color-bg-secondary);
}

.profile-form {
  display: flex;
  flex-direction: column;
  gap: 1.2rem;
}

.form-group {
  display: flex;
  flex-direction: column;
}

.form-label {
  color: var(--color-text-primary);
  font-weight: 500;
  margin-bottom: 0.4rem;
  font-size: var(--font-size-sm);
}

.required {
  color: var(--color-error);
}

.form-input {
  width: 100%;
  padding: var(--spacing-lg) var(--spacing-xl);
  border: var(--border-width) solid var(--color-border);
  border-radius: var(--radius-lg);
  background-color: var(--color-bg-secondary);
  color: var(--color-text-primary);
  font-size: var(--font-size-base);
  height: var(--input-height);
  transition: all 0.15s ease;
}

.form-select {
  width: 100%;
  padding: 0 var(--spacing-xl);
  border: var(--border-width) solid var(--color-border);
  border-radius: var(--radius-lg);
  background-color: var(--color-bg-secondary);
  color: var(--color-text-primary);
  font-size: var(--font-size-base);
  height: var(--input-height);
  transition: all 0.15s ease;
  /* Ensure proper text alignment and vertical centering */
  line-height: var(--input-height);
  appearance: none;
  background-image: url("data:image/svg+xml;charset=UTF-8,%3csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3e%3cpolyline points='6,9 12,15 18,9'%3e%3c/polyline%3e%3c/svg%3e");
  background-repeat: no-repeat;
  background-position: right var(--spacing-lg) center;
  background-size: 16px;
  padding-right: calc(var(--spacing-xl) + 24px);
}

.form-input:focus,
.form-select:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px var(--color-primary-subtle);
  background-color: var(--color-bg-primary);
}

.form-input.error,
.form-select.error {
  border-color: var(--color-error);
}

.error-message {
  color: var(--color-error);
  font-size: var(--font-size-xs);
  margin-top: 0.25rem;
}

.form-actions {
  display: flex;
  gap: 1rem;
  margin-top: 1rem;
}

.btn {
  flex: 1;
  padding: var(--spacing-lg);
  border: none;
  border-radius: var(--radius-lg);
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-medium);
  cursor: pointer;
  transition: all 0.15s ease;
  height: var(--button-height-md);
}

.btn-primary {
  background-color: var(--color-primary);
  color: white;
  font-weight: 500;
}

.btn-primary:hover:not(:disabled) {
  background-color: var(--color-primary-hover);
  color: white;
}

.btn-secondary {
  background-color: var(--color-bg-secondary);
  color: var(--color-text-primary);
  border: var(--border-width) solid var(--color-border);
}

.btn-secondary:hover:not(:disabled) {
  background-color: var(--color-bg-tertiary);
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}


</style>
