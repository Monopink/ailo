<template>
  <Teleport to="body">
    <div class="modal-overlay" @click="handleOverlayClick">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>添加联系人</h3>
          <button @click="$emit('close')" class="close-button">×</button>
        </div>

        <div class="modal-body">
          <div v-if="loading" class="loading-state">
            <div class="loading-spinner"></div>
            <p>搜索中...</p>
          </div>

          <div v-else-if="searchResults.length > 0" class="search-results">
            <h4>你还能再添加{{ remainingContactsCount }}位联系人</h4>
            <div class="contact-list">
              <div
                v-for="contact in searchResults"
                :key="contact.id"
                class="contact-item"
              >
                <ContactAvatar :nickname="contact.nickname" size="medium" />
                <div class="contact-info">
                  <div class="contact-name">{{ contact.nickname || '未知' }}</div>
                  <div class="contact-gender">{{ getGenderText(contact.gender) }}</div>
                </div>
                <button
                  class="add-btn"
                  @click="handleAddContact(contact)"
                  :disabled="addingContactId === contact.id"
                >
                  {{ addingContactId === contact.id ? '添加中...' : '添加' }}
                </button>
              </div>
            </div>
          </div>

          <div v-else-if="!loading && searchCompleted" class="no-results">
            <span class="emoji-large">🔍</span>
            <p>暂无可添加的联系人</p>
          </div>
        </div>

        <div class="modal-footer">
          <button @click="$emit('close')" class="btn btn-secondary">取消</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue';
import { useAuthStore } from '../stores/auth';
import { useChatStore } from '../stores/chat';
import { useToast } from 'vue-toastification';
import { searchContacts, addContact } from '../services/api';
import ContactAvatar from './ContactAvatar.vue';

const emit = defineEmits(['close', 'contact-added']);

const authStore = useAuthStore();
const chatStore = useChatStore();
const toast = useToast();

const loading = ref(false);
const searchCompleted = ref(false);
const searchResults = ref([]);
const addingContactId = ref(null);

// Calculate remaining contacts count
const remainingContactsCount = computed(() => {
  const limits = chatStore.contactLimits;
  return Math.max(0, limits.contact_limit - limits.current_count);
});

// Convert gender to display text
const getGenderText = (gender) => {
  switch (gender) {
    case 'male':
      return '男';
    case 'female':
      return '女';
    case 'other':
      return '其他';
    default:
      return '未知';
  }
};

// Search for contacts on component mount
onMounted(async () => {
  await performSearch();
});

const performSearch = async () => {
  if (!authStore.token) return;
  
  loading.value = true;
  searchCompleted.value = false;
  
  try {
    const response = await searchContacts('NewContacts', authStore.token);
    searchResults.value = response.data;
    searchCompleted.value = true;
  } catch (error) {
    console.error('Search contacts failed:', error);
    toast.error('搜索联系人失败');
    searchResults.value = [];
    searchCompleted.value = true;
  } finally {
    loading.value = false;
  }
};

const handleAddContact = async (contact) => {
  if (!authStore.token || addingContactId.value) return;
  
  addingContactId.value = contact.id;
  
  try {
    await addContact(contact.id, authStore.token);
    emit('contact-added');
  } catch (error) {
    console.error('Add contact failed:', error);
    const errorMessage = error.response?.data?.detail || error.message || '添加联系人失败';
    toast.error(errorMessage);
  } finally {
    addingContactId.value = null;
  }
};

const handleOverlayClick = (event) => {
  if (event.target === event.currentTarget) {
    emit('close');
  }
};
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
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.2);
  width: 90%;
  max-width: 500px;
  max-height: 80vh;
  overflow-y: auto;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.5rem;
  border-bottom: var(--border-width) solid var(--color-border);
}

.modal-header h3 {
  margin: 0;
  font-size: 1.2rem;
  font-weight: 500;
}

.close-button {
  background: none;
  border: none;
  font-size: 1.5rem;
  cursor: pointer;
  color: var(--color-text-secondary);
  width: 30px;
  height: 30px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  transition: background-color 0.2s;
}

.close-button:hover {
  background-color: var(--color-bg-secondary);
}

.modal-body {
  padding: 1.5rem;
  min-height: 200px;
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 2rem;
}

.loading-spinner {
  width: 32px;
  height: 32px;
  border: 3px solid var(--color-border);
  border-top: 3px solid var(--color-accent);
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: 1rem;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.search-results h4 {
  margin: 0 0 1rem 0;
  font-size: 1rem;
  font-weight: 500;
  color: var(--color-text-primary);
}

.contact-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.contact-item {
  display: flex;
  align-items: center;
  padding: 1rem;
  border: var(--border-width) solid var(--color-border);
  border-radius: var(--border-radius);
  background-color: var(--color-bg-secondary);
  transition: border-color 0.2s;
  gap: 1rem; /* Add gap between avatar and text */
}

.contact-item:hover {
  border-color: var(--color-accent-soft);
}



.contact-info {
  flex-grow: 1;
}

.contact-name {
  font-weight: 500;
  color: var(--color-text-primary);
  margin-bottom: 0.25rem;
}

.contact-gender {
  font-size: 0.85rem;
  color: var(--color-text-secondary);
}

.add-btn {
  padding: 0.5rem 1rem;
  border: var(--border-width) solid var(--color-accent);
  background-color: var(--color-accent);
  color: white;
  border-radius: var(--border-radius);
  cursor: pointer;
  font-size: 0.9rem;
  transition: all 0.2s;
}

.add-btn:hover:not(:disabled) {
  background-color: var(--color-accent-dark);
  border-color: var(--color-accent-dark);
}

.add-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.no-results {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 2rem;
  color: var(--color-text-secondary);
  text-align: center;
}

.emoji-large {
  font-size: 3rem;
  margin-bottom: 1rem;
}

.modal-footer {
  padding: 1rem 1.5rem;
  border-top: var(--border-width) solid var(--color-border);
  display: flex;
  justify-content: flex-end;
}

.btn {
  padding: 0.5rem 1rem;
  border-radius: var(--border-radius);
  cursor: pointer;
  font-size: 0.9rem;
  transition: all 0.2s;
}

.btn-secondary {
  border: var(--border-width) solid var(--color-border);
  background-color: var(--color-bg-secondary);
  color: var(--color-text-primary);
}

.btn-secondary:hover {
  background-color: var(--color-bg-primary);
}
</style>
