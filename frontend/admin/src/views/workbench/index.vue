<template>
  <div class="workbench-container">
    <div class="workbench-header">
      <h1 class="workbench-title">Dashboard</h1>
      <p class="workbench-subtitle">Welcome to Says Admin</p>
    </div>

    <div class="workbench-content">
      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-icon">👥</div>
          <div class="stat-info">
            <h3>Users</h3>
            <p class="stat-number">1,234</p>
          </div>
        </div>

        <div class="stat-card">
          <div class="stat-icon">🤖</div>
          <div class="stat-info">
            <h3>Bots</h3>
            <p class="stat-number">56</p>
          </div>
        </div>

        <div class="stat-card">
          <div class="stat-icon">💬</div>
          <div class="stat-info">
            <h3>Messages</h3>
            <p class="stat-number">12,345</p>
          </div>
        </div>

        <div class="stat-card">
          <div class="stat-icon">📊</div>
          <div class="stat-info">
            <h3>Active Sessions</h3>
            <p class="stat-number">89</p>
          </div>
        </div>
      </div>

      <div class="recent-activity">
        <h2>Recent Activity</h2>
        <div class="activity-list">
          <div class="activity-item">
            <span class="activity-time">2 minutes ago</span>
            <span class="activity-text">New user registered</span>
          </div>
          <div class="activity-item">
            <span class="activity-time">5 minutes ago</span>
            <span class="activity-text">Bot conversation started</span>
          </div>
          <div class="activity-item">
            <span class="activity-time">10 minutes ago</span>
            <span class="activity-text">System maintenance completed</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
// Simple dashboard component
</script>

<style scoped>
.workbench-container {
  padding: var(--spacing-xl);
  max-width: 1200px;
  margin: 0 auto;
}

.workbench-header {
  margin-bottom: var(--spacing-2xl);
}

.workbench-title {
  font-size: var(--font-size-3xl);
  font-weight: 600;
  color: var(--color-text-primary);
  margin: 0 0 var(--spacing-sm) 0;
}

.workbench-subtitle {
  font-size: var(--font-size-lg);
  color: var(--color-text-secondary);
  margin: 0;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: var(--spacing-lg);
  margin-bottom: var(--spacing-2xl);
}

.stat-card {
  background: var(--color-bg-primary);
  border: 1px solid var(--color-border-primary);
  border-radius: var(--radius-lg);
  padding: var(--spacing-lg);
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  transition: all var(--transition-fast);
}

.stat-card:hover {
  box-shadow: var(--shadow-md);
  transform: translateY(-2px);
}

.stat-icon {
  font-size: 32px;
  width: 60px;
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-bg-secondary);
  border-radius: var(--radius-md);
}

.stat-info h3 {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  margin: 0 0 var(--spacing-xs) 0;
  font-weight: 500;
}

.stat-number {
  font-size: var(--font-size-2xl);
  font-weight: 600;
  color: var(--color-text-primary);
  margin: 0;
}

.recent-activity {
  background: var(--color-bg-primary);
  border: 1px solid var(--color-border-primary);
  border-radius: var(--radius-lg);
  padding: var(--spacing-lg);
}

.recent-activity h2 {
  font-size: var(--font-size-xl);
  font-weight: 600;
  color: var(--color-text-primary);
  margin: 0 0 var(--spacing-lg) 0;
}

.activity-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.activity-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-sm) 0;
  border-bottom: 1px solid var(--color-border-primary);
}

.activity-item:last-child {
  border-bottom: none;
}

.activity-time {
  font-size: var(--font-size-sm);
  color: var(--color-text-tertiary);
}

.activity-text {
  font-size: var(--font-size-sm);
  color: var(--color-text-primary);
}

@media (max-width: 768px) {
  .workbench-container {
    padding: var(--spacing-lg);
  }

  .stats-grid {
    grid-template-columns: 1fr;
  }

  .activity-item {
    flex-direction: column;
    align-items: flex-start;
    gap: var(--spacing-xs);
  }
}
</style>
