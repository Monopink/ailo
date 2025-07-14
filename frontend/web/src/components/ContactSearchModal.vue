<template>
  <Teleport to="body">
    <div
      class="modal-overlay"
      @click="handleOverlayClick"
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-title">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3 id="modal-title">添加联系人</h3>
          <button
            @click="$emit('close')"
            class="close-button"
            type="button"
            aria-label="关闭对话框">
            ×
          </button>
        </div>

        <div class="modal-body">
          <div v-if="loading" class="loading-state" aria-live="polite">
            <div class="loading-spinner" aria-hidden="true"></div>
            <p>搜索中...</p>
          </div>

          <div v-else-if="searchResults.length > 0" class="search-results">
            <h4 id="search-results-heading">你还能再添加{{ remainingContactsCount }}位联系人</h4>
            <div
              class="contact-list"
              role="list"
              aria-labelledby="search-results-heading">
              <div
                v-for="contact in searchResults"
                :key="contact.id"
                class="contact-item"
                role="listitem"
              >
                <ContactAvatar :nickname="contact.nickname" size="medium" />
                <div class="contact-info">
                  <div class="contact-name">{{ contact.nickname || '' }}</div>
                  <div class="contact-gender" v-if="getGenderEmoji(contact.gender)">
                    <span class="gender-emoji">{{ getGenderEmoji(contact.gender) }}</span>
                  </div>
                </div>
                <button
                  class="btn btn-primary btn-sm"
                  @click="handleAddContact(contact)"
                  :disabled="addingContactId === contact.id"
                  type="button"
                  :aria-label="`添加联系人 ${contact.nickname || '未知'}`"
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
import { ref, onMounted, onUnmounted, computed, nextTick } from 'vue';
import { useAuthStore } from '../stores/auth';
import { useChatStore } from '../stores/chat';
import { apiClient } from '../utils/apiHelpers';
import ContactAvatar from './ContactAvatar.vue';
import { uiLogger } from '../utils/logger.js';
import { handleError } from '../utils/errorHandler.js';

const emit = defineEmits(['close', 'contact-added']);

const authStore = useAuthStore();
const chatStore = useChatStore();

const loading = ref(false);
const searchCompleted = ref(false);
const searchResults = ref([]);
const addingContactId = ref(null);

// Calculate remaining contacts count
const remainingContactsCount = computed(() => {
  const limits = chatStore.contactLimits;
  return Math.max(0, limits.contact_limit - limits.current_count);
});

// Convert gender to display emoji
const getGenderEmoji = (gender) => {
  switch (gender) {
    case 'male':
      return '🙋🏻‍♂️';
    case 'female':
      return '🙋🏻‍♀️';
    default:
      return ''; // Don't show anything for 'other' or unknown
  }
};

// Search for contacts on component mount
onMounted(async () => {
  await performSearch();
  // Focus management for accessibility
  await nextTick();
  const modalContent = document.querySelector('.modal-content');
  if (modalContent) {
    modalContent.focus();
  }
});

// Keyboard event handling
const handleKeyDown = (event) => {
  if (event.key === 'Escape') {
    emit('close');
  }
};

// Add global keyboard listener
onMounted(() => {
  document.addEventListener('keydown', handleKeyDown);
  uiLogger.debug('ContactSearchModal mounted');
});

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeyDown);
  uiLogger.debug('ContactSearchModal unmounted');
});

const performSearch = async () => {
  if (!authStore.token) {
    uiLogger.warn('No auth token available for contact search');
    return;
  }

  loading.value = true;
  searchCompleted.value = false;

  try {
    uiLogger.debug('Searching for new contacts');
    const response = await apiClient.get('/contacts/search?query=NewContacts');
    const searchData = response.data.data || response.data;
    searchResults.value = searchData;
    searchCompleted.value = true;
    uiLogger.info('Contact search completed', { resultCount: searchData.length });
  } catch (error) {
    uiLogger.error('Contact search failed', error);
    handleError(error, {
      operation: 'search_contacts',
      context: 'ContactSearchModal',
      showToast: false,
    });
    searchResults.value = [];
    searchCompleted.value = true;
  } finally {
    loading.value = false;
  }
};

const handleAddContact = async (contact) => {
  if (!authStore.token || addingContactId.value) return;

  addingContactId.value = contact.id;
  uiLogger.debug('Adding contact', { contactId: contact.id, nickname: contact.nickname });

  try {
    await apiClient.post('/contacts/add', { contact_id: contact.id });
    uiLogger.info('Contact added successfully', { contactId: contact.id });
    emit('contact-added');
  } catch (error) {
    uiLogger.error('Add contact failed', { contactId: contact.id, error });
    handleError(error, {
      operation: 'add_contact',
      context: 'ContactSearchModal',
      showToast: true,
    });
  } finally {
    addingContactId.value = null;
  }
};

const handleOverlayClick = (event) => {
  if (event.target === event.currentTarget) {
    uiLogger.debug('Modal closed by overlay click');
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
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-xl);
  border: var(--border-width) solid var(--color-border);
  width: 90%;
  max-width: 480px;
  max-height: 80vh;
  overflow-y: auto;
  outline: none;
}

.modal-content:focus {
  outline: none;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-3xl);
  padding-bottom: var(--spacing-xl);
}

.modal-header h3 {
  margin: 0;
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
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
  transition: background-color 0.2s, box-shadow 0.2s;
}

.close-button:hover {
  background-color: var(--color-bg-secondary);
}

.close-button:focus {
  outline: none;
}

.close-button:hover {
  background-color: var(--color-bg-secondary);
}

.modal-body {
  padding: var(--spacing-2xl);
  min-height: 200px;
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--spacing-3xl);
}

.loading-spinner {
  width: 32px;
  height: 32px;
  border: 3px solid var(--color-border);
  border-top: 3px solid var(--color-accent);
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: var(--spacing-lg);
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.search-results h4 {
  margin: 0 0 var(--spacing-lg) 0;
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-normal);
  color: var(--color-text-secondary);
}

.contact-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.contact-item {
  display: flex;
  align-items: center;
  padding: var(--spacing-xl);
  border-radius: var(--radius-md);
  background-color: var(--color-bg-secondary);
  transition: all 0.2s ease;
  gap: var(--spacing-xl);
  border: none;
}

.contact-item:hover {
  background-color: var(--color-bg-tertiary);
}



.contact-info {
  flex-grow: 1;
}

.contact-name {
  font-weight: 500;
  color: var(--color-text-primary);
  margin-bottom: var(--spacing-xs);
  min-height: 1.2em; /* Ensure space is reserved even when empty */
}

.contact-gender {
  display: flex;
  align-items: center;
}

.gender-emoji {
  font-size: 16px;
}

/* Removed .add-btn styles - now using unified .btn classes */

.no-results {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--spacing-3xl);
  color: var(--color-text-secondary);
  text-align: center;
}

.emoji-large {
  font-size: 3rem;
  margin-bottom: var(--spacing-lg);
}

.modal-footer {
  padding: var(--spacing-lg) var(--spacing-2xl);
  border-top: var(--border-width) solid var(--color-border);
  display: flex;
  justify-content: flex-end;
}

/* Removed duplicate .btn styles - now using unified .btn classes from main.css */
</style>
