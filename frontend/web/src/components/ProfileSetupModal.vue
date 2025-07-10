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
import { useToast } from 'vue-toastification'

const emit = defineEmits(['close', 'success'])

const authStore = useAuthStore()
const toast = useToast()

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
    
    toast.success('个人资料设置成功！')
    emit('success')
    emit('close')
  } catch (error) {
    const errorMessage = error.response?.data?.detail || '设置失败，请稍后重试'
    toast.error(errorMessage)
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
  border-radius: var(--border-radius);
  padding: 1.5rem;
  width: 90%;
  max-width: 350px;
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.2);
}

.modal-header {
  text-align: center;
  margin-bottom: 1.5rem;
}

.modal-header h2 {
  color: var(--color-text-primary);
  margin-bottom: 0.5rem;
  font-size: 1.1rem;
  font-weight: 500;
}

.modal-subtitle {
  color: var(--color-text-secondary);
  font-size: 0.8rem;
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
  font-size: 0.85rem;
}

.required {
  color: var(--color-error);
}

.form-input,
.form-select {
  padding: 0.6rem;
  border: var(--border-width) solid var(--color-border);
  border-radius: var(--border-radius-sm);
  background-color: var(--color-bg-primary);
  color: var(--color-text-primary);
  font-size: 0.85rem;
  transition: border-color 0.2s;
}

.form-input:focus,
.form-select:focus {
  outline: none;
  border-color: var(--color-accent);
}

.form-input.error,
.form-select.error {
  border-color: var(--color-error);
}

.error-message {
  color: var(--color-error);
  font-size: 0.8rem;
  margin-top: 0.25rem;
}

.form-actions {
  margin-top: 1rem;
}

.btn {
  width: 100%;
  padding: 0.6rem;
  border: none;
  border-radius: var(--border-radius-sm);
  font-size: 0.85rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
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

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
