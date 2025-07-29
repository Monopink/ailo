<template>
  <div class="components-container">
    <!-- Breadcrumb -->
    <nav class="breadcrumb">
      <span class="breadcrumb-item">Dashboard</span>
      <span class="breadcrumb-separator">></span>
      <span class="breadcrumb-item breadcrumb-current">Components</span>
    </nav>

    <div class="components-header">
      <h1 class="components-title">Design System Components</h1>
      <p class="components-subtitle">All available UI components and design elements</p>
    </div>

    <div class="components-content">
      <!-- Buttons Section -->
      <section class="component-section">
        <h2 class="section-title">Buttons</h2>
        <div class="component-demo">
          <div class="demo-group">
            <h3 class="demo-title">Primary Buttons</h3>
            <div class="demo-items">
              <button class="btn btn-primary">Primary</button>
              <button class="btn btn-primary" disabled>Disabled</button>
              <button class="btn btn-primary btn-loading">Loading...</button>
            </div>
          </div>

          <div class="demo-group">
            <h3 class="demo-title">Secondary Buttons</h3>
            <div class="demo-items">
              <button class="btn btn-secondary">Secondary</button>
              <button class="btn btn-secondary" disabled>Disabled</button>
            </div>
          </div>

          <div class="demo-group">
            <h3 class="demo-title">Danger Buttons</h3>
            <div class="demo-items">
              <button class="btn btn-danger">Delete</button>
              <button class="btn btn-danger" disabled>Disabled</button>
            </div>
          </div>

          <div class="demo-group">
            <h3 class="demo-title">Button Sizes</h3>
            <div class="demo-items">
              <button class="btn btn-primary btn-sm">Small</button>
              <button class="btn btn-primary">Default</button>
              <button class="btn btn-primary btn-lg">Large</button>
            </div>
          </div>
        </div>
      </section>

      <!-- Form Elements Section -->
      <section class="component-section">
        <h2 class="section-title">Form Elements</h2>
        <div class="component-demo">
          <div class="demo-group">
            <h3 class="demo-title">Input Fields</h3>
            <div class="demo-form">
              <div class="form-group">
                <label class="form-label">Text Input</label>
                <input type="text" class="input" placeholder="Enter text..." />
              </div>
              
              <div class="form-group">
                <label class="form-label">Password Input</label>
                <input type="password" class="input" placeholder="Enter password..." />
              </div>
              
              <div class="form-group">
                <label class="form-label">Disabled Input</label>
                <input type="text" class="input" value="Disabled field" disabled />
              </div>
            </div>
          </div>

          <div class="demo-group">
            <h3 class="demo-title">Select & Textarea</h3>
            <div class="demo-form">
              <div class="form-group">
                <label class="form-label">Select</label>
                <select class="input">
                  <option>Option 1</option>
                  <option>Option 2</option>
                  <option>Option 3</option>
                </select>
              </div>
              
              <div class="form-group">
                <label class="form-label">Textarea</label>
                <textarea class="input" rows="3" placeholder="Enter description..."></textarea>
              </div>
            </div>
          </div>

          <div class="demo-group">
            <h3 class="demo-title">Checkboxes & Radio</h3>
            <div class="demo-form">
              <div class="form-group">
                <label class="checkbox-label">
                  <input type="checkbox" class="checkbox" />
                  <span class="checkbox-text">Checkbox option</span>
                </label>
              </div>
              
              <div class="form-group">
                <label class="radio-label">
                  <input type="radio" name="radio-demo" class="radio" />
                  <span class="radio-text">Radio option 1</span>
                </label>
                <label class="radio-label">
                  <input type="radio" name="radio-demo" class="radio" />
                  <span class="radio-text">Radio option 2</span>
                </label>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- Cards Section -->
      <section class="component-section">
        <h2 class="section-title">Cards</h2>
        <div class="component-demo">
          <div class="demo-group">
            <h3 class="demo-title">Basic Cards</h3>
            <div class="demo-cards">
              <div class="card">
                <div class="card-header">
                  <h4>Card Title</h4>
                </div>
                <div class="card-body">
                  <p>This is a basic card with header and body content.</p>
                </div>
                <div class="card-footer">
                  <button class="btn btn-primary btn-sm">Action</button>
                </div>
              </div>

              <div class="card card-modern">
                <div class="card-body">
                  <h4>Modern Card</h4>
                  <p>This is a modern card with backdrop blur effect.</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- Status & Alerts Section -->
      <section class="component-section">
        <h2 class="section-title">Status & Alerts</h2>
        <div class="component-demo">
          <div class="demo-group">
            <h3 class="demo-title">Status Badges</h3>
            <div class="demo-items">
              <span class="badge badge-success">Success</span>
              <span class="badge badge-warning">Warning</span>
              <span class="badge badge-error">Error</span>
              <span class="badge badge-info">Info</span>
            </div>
          </div>

          <div class="demo-group">
            <h3 class="demo-title">Alert Messages</h3>
            <div class="demo-alerts">
              <div class="alert alert-success">
                <strong>Success!</strong> Operation completed successfully.
              </div>
              <div class="alert alert-warning">
                <strong>Warning!</strong> Please check your input.
              </div>
              <div class="alert alert-error">
                <strong>Error!</strong> Something went wrong.
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- Tables Section -->
      <section class="component-section">
        <h2 class="section-title">Tables</h2>
        <div class="component-demo">
          <div class="demo-group">
            <h3 class="demo-title">Data Table</h3>
            <div class="table-container">
              <table class="table">
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Name</th>
                    <th>Email</th>
                    <th>Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>1</td>
                    <td>John Doe</td>
                    <td>john@example.com</td>
                    <td><span class="badge badge-success">Active</span></td>
                    <td>
                      <div class="action-buttons">
                        <button class="btn btn-secondary btn-sm">Edit</button>
                        <button class="btn btn-danger btn-sm">Delete</button>
                      </div>
                    </td>
                  </tr>
                  <tr>
                    <td>2</td>
                    <td>Jane Smith</td>
                    <td>jane@example.com</td>
                    <td><span class="badge badge-warning">Pending</span></td>
                    <td>
                      <div class="action-buttons">
                        <button class="btn btn-secondary btn-sm">Edit</button>
                        <button class="btn btn-danger btn-sm">Delete</button>
                      </div>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </section>

      <!-- Loading States -->
      <section class="component-section">
        <h2 class="section-title">Loading States</h2>
        <div class="component-demo">
          <div class="demo-group">
            <h3 class="demo-title">Spinners</h3>
            <div class="demo-items">
              <div class="spinner"></div>
              <div class="spinner spinner-sm"></div>
              <div class="spinner spinner-lg"></div>
            </div>
          </div>
        </div>
      </section>

      <!-- Theme Testing -->
      <section class="component-section">
        <h2 class="section-title">Theme Testing</h2>
        <div class="component-demo">
          <div class="demo-group">
            <h3 class="demo-title">Current Theme</h3>
            <div class="theme-info">
              <p><strong>Theme Setting:</strong> {{ theme }}</p>
              <p><strong>Effective Theme:</strong> {{ effectiveTheme }}</p>
              <p><strong>Is Dark:</strong> {{ isDark }}</p>
            </div>
          </div>

          <div class="demo-group">
            <h3 class="demo-title">Theme Controls</h3>
            <div class="demo-items">
              <button class="btn btn-primary" @click="setTheme('light')">Light</button>
              <button class="btn btn-primary" @click="setTheme('dark')">Dark</button>
              <button class="btn btn-primary" @click="setTheme('auto')">Auto</button>
              <button class="btn btn-secondary" @click="toggleTheme">Toggle</button>
            </div>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
// Component showcase page
import { ref, onMounted, onUnmounted } from 'vue'
import themeManager from '@/utils/theme.js'

// Reactive theme state
const theme = ref(themeManager.getTheme())
const effectiveTheme = ref(themeManager.getEffectiveTheme())
const isDark = ref(themeManager.isDark())

// Theme change listener
const handleThemeChange = (themeData) => {
  theme.value = themeData.theme
  effectiveTheme.value = themeData.effectiveTheme
  isDark.value = themeData.effectiveTheme === 'dark'
}

// Theme control functions
const setTheme = (newTheme) => {
  themeManager.setTheme(newTheme)
}

const toggleTheme = () => {
  themeManager.toggleTheme()
}

// Lifecycle hooks
onMounted(() => {
  themeManager.addListener(handleThemeChange)
})

onUnmounted(() => {
  themeManager.removeListener(handleThemeChange)
})
</script>

<style scoped>
.components-container {
  padding: var(--spacing-xl);
  max-width: 1200px;
  margin: 0 auto;
}

/* Breadcrumb */
.breadcrumb {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  margin-bottom: var(--spacing-lg);
  font-size: var(--font-size-sm);
}

.breadcrumb-item {
  color: var(--color-text-secondary);
}

.breadcrumb-current {
  color: var(--color-text-primary);
  font-weight: 500;
}

.breadcrumb-separator {
  color: var(--color-text-tertiary);
}

/* Header */
.components-header {
  margin-bottom: var(--spacing-2xl);
}

.components-title {
  font-size: var(--font-size-3xl);
  font-weight: 600;
  color: var(--color-text-primary);
  margin: 0 0 var(--spacing-sm) 0;
}

.components-subtitle {
  font-size: var(--font-size-lg);
  color: var(--color-text-secondary);
  margin: 0;
}

/* Sections */
.component-section {
  margin-bottom: var(--spacing-2xl);
  background: var(--color-bg-primary);
  border: 1px solid var(--color-border-primary);
  border-radius: var(--radius-lg);
  padding: var(--spacing-xl);
}

.section-title {
  font-size: var(--font-size-xl);
  font-weight: 600;
  color: var(--color-text-primary);
  margin: 0 0 var(--spacing-lg) 0;
  padding-bottom: var(--spacing-sm);
  border-bottom: 1px solid var(--color-border-primary);
}

/* Demo Groups */
.demo-group {
  margin-bottom: var(--spacing-xl);
}

.demo-group:last-child {
  margin-bottom: 0;
}

.demo-title {
  font-size: var(--font-size-base);
  font-weight: 500;
  color: var(--color-text-secondary);
  margin: 0 0 var(--spacing-md) 0;
}

.demo-items {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  flex-wrap: wrap;
}

.demo-form {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: var(--spacing-lg);
}

.demo-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: var(--spacing-lg);
}

.demo-alerts {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

/* Form Elements */
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

.checkbox-label,
.radio-label {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  cursor: pointer;
}

/* Action buttons */
.action-buttons {
  display: flex;
  gap: var(--spacing-sm);
}

/* Theme testing styles */
.theme-info {
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-border-primary);
  border-radius: var(--radius-md);
  padding: var(--spacing-md);
  font-family: monospace;
  font-size: var(--font-size-sm);
}

.theme-info p {
  margin: var(--spacing-xs) 0;
  color: var(--color-text-primary);
}

/* Additional component styles would be imported from global.scss */
</style>
