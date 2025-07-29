<template>
  <div class="admin-users-page">
    <div class="page-header">
      <h2>Admin Users Management</h2>
      <button class="btn btn-primary" @click="alert('Create user functionality coming soon')">
        Add User
      </button>
    </div>

    <!-- User List -->
    <div class="user-list">
      <div class="search-bar">
        <input 
          v-model="searchForm.username" 
          type="text" 
          placeholder="Search by username..."
          @input="handleSearch"
        >
        <select v-model="searchForm.role" @change="handleSearch">
          <option value="">All Roles</option>
          <option value="super_admin">Super Admin</option>
          <option value="admin">Admin</option>
          <option value="viewer">Viewer</option>
        </select>
      </div>

      <div class="table-container">
        <table class="table">
          <thead>
            <tr>
              <th @click="sortBy('id')" class="sortable">
                <span class="sort-header">
                  ID
                  <span class="sort-indicator">
                    <span v-if="sortField === 'id'" class="sort-arrow">
                      {{ sortOrder === 'asc' ? '↑' : '↓' }}
                    </span>
                  </span>
                </span>
              </th>
              <th @click="sortBy('username')" class="sortable">
                <span class="sort-header">
                  Username
                  <span class="sort-indicator">
                    <span v-if="sortField === 'username'" class="sort-arrow">
                      {{ sortOrder === 'asc' ? '↑' : '↓' }}
                    </span>
                  </span>
                </span>
              </th>
              <th @click="sortBy('email')" class="sortable">
                <span class="sort-header">
                  Email
                  <span class="sort-indicator">
                    <span v-if="sortField === 'email'" class="sort-arrow">
                      {{ sortOrder === 'asc' ? '↑' : '↓' }}
                    </span>
                  </span>
                </span>
              </th>
              <th @click="sortBy('real_name')" class="sortable">
                <span class="sort-header">
                  Real Name
                  <span class="sort-indicator">
                    <span v-if="sortField === 'real_name'" class="sort-arrow">
                      {{ sortOrder === 'asc' ? '↑' : '↓' }}
                    </span>
                  </span>
                </span>
              </th>
              <th @click="sortBy('role')" class="sortable">
                <span class="sort-header">
                  Role
                  <span class="sort-indicator">
                    <span v-if="sortField === 'role'" class="sort-arrow">
                      {{ sortOrder === 'asc' ? '↑' : '↓' }}
                    </span>
                  </span>
                </span>
              </th>
              <th @click="sortBy('is_active')" class="sortable">
                <span class="sort-header">
                  Status
                  <span class="sort-indicator">
                    <span v-if="sortField === 'is_active'" class="sort-arrow">
                      {{ sortOrder === 'asc' ? '↑' : '↓' }}
                    </span>
                  </span>
                </span>
              </th>
              <th @click="sortBy('last_login')" class="sortable">
                <span class="sort-header">
                  Last Login
                  <span class="sort-indicator">
                    <span v-if="sortField === 'last_login'" class="sort-arrow">
                      {{ sortOrder === 'asc' ? '↑' : '↓' }}
                    </span>
                  </span>
                </span>
              </th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="user in users" :key="user.id">
              <td>{{ user.id }}</td>
              <td>{{ user.username }}</td>
              <td>{{ user.email || '-' }}</td>
              <td>{{ user.real_name || '-' }}</td>
              <td>
                <span :class="['badge', getRoleBadgeClass(user.role)]">
                  {{ getRoleDisplay(user.role) }}
                </span>
              </td>
              <td>
                <span :class="['badge', user.is_active ? 'badge-success' : 'badge-error']">
                  {{ user.is_active ? 'Active' : 'Inactive' }}
                </span>
              </td>
              <td>{{ formatDate(user.last_login) }}</td>
              <td>
                <div class="action-buttons">
                  <button class="btn btn-sm btn-secondary" @click="alert('Edit functionality coming soon')">
                    Edit
                  </button>
                  <button
                    class="btn btn-sm btn-warning"
                    @click="alert('Reset password functionality coming soon')"
                    v-if="user.role !== 'super_admin'"
                  >
                    Reset Password
                  </button>
                  <button
                    class="btn btn-sm btn-danger"
                    @click="alert('Delete functionality coming soon')"
                    v-if="user.role !== 'super_admin' && user.id !== currentUser?.id"
                  >
                    Delete
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Pagination -->
      <div class="pagination" v-if="total > pageSize">
        <button 
          class="btn btn-sm" 
          :disabled="page <= 1"
          @click="changePage(page - 1)"
        >
          Previous
        </button>
        <span class="page-info">
          Page {{ page }} of {{ Math.ceil(total / pageSize) }}
        </span>
        <button 
          class="btn btn-sm" 
          :disabled="page >= Math.ceil(total / pageSize)"
          @click="changePage(page + 1)"
        >
          Next
        </button>
      </div>
    </div>

    <!-- Modals will be added later -->

    <!-- Loading -->
    <div v-if="loading" class="loading">Loading...</div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import api from '@/api'
import { useAuthStore } from '@/store'

const authStore = useAuthStore()
const currentUser = computed(() => authStore.user)

// Data
const users = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)

// Sorting
const sortField = ref('')
const sortOrder = ref('asc')

// Forms
const searchForm = reactive({
  username: '',
  role: ''
})

// Methods
const fetchUsers = async () => {
  loading.value = true
  try {
    const params = {
      page: page.value,
      page_size: pageSize.value,
      username: searchForm.username,
      role: searchForm.role
    }
    
    const response = await api.getUserList(params)
    console.log('API Response:', response) // Debug log
    users.value = response.data || []
    total.value = response.total || 0
  } catch (error) {
    console.error('Failed to fetch users:', error)
    alert('Failed to fetch users')
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  page.value = 1
  fetchUsers()
}

const changePage = (newPage) => {
  page.value = newPage
  fetchUsers()
}

// Sorting functionality
const sortBy = (field) => {
  if (sortField.value === field) {
    // Toggle sort order if clicking the same field
    sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc'
  } else {
    // Set new field and default to ascending
    sortField.value = field
    sortOrder.value = 'asc'
  }

  // Sort the current data
  sortUsers()
}

const sortUsers = () => {
  if (!sortField.value) return

  users.value.sort((a, b) => {
    let aVal = a[sortField.value]
    let bVal = b[sortField.value]

    // Handle null/undefined values
    if (aVal == null) aVal = ''
    if (bVal == null) bVal = ''

    // Convert to string for comparison
    aVal = String(aVal).toLowerCase()
    bVal = String(bVal).toLowerCase()

    if (sortOrder.value === 'asc') {
      return aVal.localeCompare(bVal)
    } else {
      return bVal.localeCompare(aVal)
    }
  })
}

// Modal functions will be added later

const formatDate = (dateString) => {
  if (!dateString) return '-'
  return new Date(dateString).toLocaleString()
}

const getRoleDisplay = (role) => {
  const roleMap = {
    'super_admin': 'Super Admin',
    'admin': 'Admin',
    'viewer': 'Viewer'
  }
  return roleMap[role] || role
}

const getRoleBadgeClass = (role) => {
  const classMap = {
    'super_admin': 'badge-error',
    'admin': 'badge-info',
    'viewer': 'badge-success'
  }
  return classMap[role] || 'badge-info'
}

// Lifecycle
onMounted(() => {
  fetchUsers()
})
</script>

<style scoped>
.admin-users-page {
  padding: var(--spacing-xl);
  max-width: 1200px;
  margin: 0 auto;
}

.page-header {
  margin-bottom: var(--spacing-2xl);
}

.page-header h2 {
  font-size: var(--font-size-3xl);
  font-weight: 600;
  color: var(--color-text-primary);
  margin: 0 0 var(--spacing-sm) 0;
}

.search-bar {
  display: flex;
  gap: var(--spacing-md);
  margin-bottom: var(--spacing-xl);
}

.search-bar input,
.search-bar select {
  padding: var(--spacing-sm) var(--spacing-md);
  border: 1px solid var(--color-border-primary);
  border-radius: var(--radius-md);
  background: var(--color-bg-primary);
  color: var(--color-text-primary);
  font-size: var(--font-size-base);
  transition: var(--transition-fast);
}

.search-bar input:focus,
.search-bar select:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px var(--color-primary-light);
}

/* Table sorting styles */
.sortable {
  cursor: pointer;
  user-select: text;
  position: relative;
  transition: background-color var(--transition-fast);
}

.sortable:hover {
  background-color: var(--color-bg-tertiary);
}

.sort-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

.sort-indicator {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  margin-left: var(--spacing-xs);
}

.sort-arrow {
  font-size: var(--font-size-xs);
  color: var(--color-primary);
  line-height: 1;
}

.action-buttons {
  display: flex;
  gap: var(--spacing-sm);
}

.pagination {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: var(--spacing-md);
  margin-top: var(--spacing-xl);
}

.page-info {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}

.loading {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  background: var(--color-bg-overlay);
  color: var(--color-text-inverse);
  padding: var(--spacing-lg);
  border-radius: var(--radius-lg);
  z-index: 1000;
}
</style>
