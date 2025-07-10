<template>
  <div class="test-container">
    <h1>LeanMessage Connection Test</h1>
    
    <div class="status-section">
      <h2>Status</h2>
      <p>Connection: <span :class="statusClass">{{ status }}</span></p>
      <p v-if="error" class="error">Error: {{ error }}</p>
    </div>
    
    <div class="test-section">
      <h2>Test Connection</h2>
      <div class="form-group">
        <label>Client ID:</label>
        <input v-model="clientId" placeholder="Enter test client ID" />
      </div>
      <button @click="testConnection" :disabled="loading" class="test-btn">
        {{ loading ? 'Testing...' : 'Test Connection' }}
      </button>
    </div>
    
    <div class="logs-section">
      <h2>Logs</h2>
      <div class="logs">
        <div v-for="(log, index) in logs" :key="index" class="log-entry">
          {{ log }}
        </div>
      </div>
      <button @click="clearLogs" class="clear-btn">Clear Logs</button>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { Realtime } from 'leancloud-realtime'

const status = ref('Not connected')
const error = ref('')
const loading = ref(false)
const clientId = ref('test123')
const logs = ref([])

let realtime = null
let client = null

const statusClass = ref('status-disconnected')

const addLog = (message) => {
  const timestamp = new Date().toLocaleTimeString()
  logs.value.push(`[${timestamp}] ${message}`)
}

const clearLogs = () => {
  logs.value = []
}

const testConnection = async () => {
  loading.value = true
  error.value = ''
  
  try {
    addLog('Starting LeanMessage connection test...')
    
    // Get environment variables
    const appId = import.meta.env.VITE_LEANCLOUD_APP_ID
    const appKey = import.meta.env.VITE_LEANCLOUD_APP_KEY
    const serverURL = import.meta.env.VITE_LEANCLOUD_SERVER_URL
    
    addLog(`App ID: ${appId ? appId.substring(0, 8) + '...' : 'Not set'}`)
    addLog(`App Key: ${appKey ? 'Set' : 'Not set'}`)
    addLog(`Server URL: ${serverURL || 'Not set'}`)
    
    if (!appId || !appKey) {
      throw new Error('Missing LeanMessage credentials in environment variables')
    }
    
    // Initialize Realtime
    addLog('Initializing LeanMessage Realtime...')
    
    const options = {
      appId,
      appKey,
      debug: true
    }
    
    // Configure server based on region
    if (serverURL === 'CN') {
      options.server = 'https://zcuk19lc.lc-cn-n1-shared.com'
      addLog('Using CN region server')
    } else if (serverURL === 'US') {
      options.server = 'https://rtm-router.leancloud.app'
      addLog('Using US region server')
    } else if (serverURL) {
      options.server = serverURL
      addLog(`Using custom server: ${serverURL}`)
    }
    
    realtime = new Realtime(options)
    addLog('✅ LeanMessage Realtime initialized')
    
    // Create IM Client
    addLog(`Creating IM client with ID: ${clientId.value}`)
    client = await realtime.createIMClient(clientId.value)
    addLog('✅ IM client created successfully')
    
    // Set up event listeners
    client.on('disconnect', () => {
      addLog('❌ Client disconnected')
      status.value = 'Disconnected'
      statusClass.value = 'status-disconnected'
    })
    
    client.on('reconnect', () => {
      addLog('✅ Client reconnected')
      status.value = 'Connected'
      statusClass.value = 'status-connected'
    })
    
    client.on('reconnecterror', (error) => {
      addLog(`❌ Reconnection error: ${error.message}`)
      status.value = 'Error'
      statusClass.value = 'status-error'
    })
    
    status.value = 'Connected'
    statusClass.value = 'status-connected'
    addLog('🎉 Connection test completed successfully!')
    
  } catch (err) {
    console.error('Connection test failed:', err)
    error.value = err.message
    status.value = 'Error'
    statusClass.value = 'status-error'
    addLog(`❌ Connection test failed: ${err.message}`)
  } finally {
    loading.value = false
  }
}

const disconnect = async () => {
  if (client) {
    try {
      await client.close()
      addLog('✅ Client disconnected')
      status.value = 'Disconnected'
      statusClass.value = 'status-disconnected'
      client = null
      realtime = null
    } catch (err) {
      addLog(`❌ Disconnect error: ${err.message}`)
    }
  }
}

// Cleanup on component unmount
import { onUnmounted } from 'vue'
onUnmounted(() => {
  disconnect()
})
</script>

<style scoped>
.test-container {
  max-width: 800px;
  margin: 0 auto;
  padding: 20px;
  font-family: Arial, sans-serif;
}

h1 {
  color: #333;
  text-align: center;
  margin-bottom: 30px;
}

h2 {
  color: #555;
  border-bottom: 2px solid #eee;
  padding-bottom: 10px;
  margin-bottom: 20px;
}

.status-section, .test-section, .logs-section {
  background: #f9f9f9;
  padding: 20px;
  margin-bottom: 20px;
  border-radius: 8px;
  border: 1px solid #ddd;
}

.status-connected {
  color: #28a745;
  font-weight: bold;
}

.status-disconnected {
  color: #6c757d;
  font-weight: bold;
}

.status-error {
  color: #dc3545;
  font-weight: bold;
}

.error {
  color: #dc3545;
  font-weight: bold;
  margin-top: 10px;
}

.form-group {
  margin-bottom: 15px;
}

.form-group label {
  display: block;
  margin-bottom: 5px;
  font-weight: bold;
  color: #555;
}

.form-group input {
  width: 100%;
  padding: 10px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 14px;
}

.test-btn, .clear-btn {
  background: #07c160;
  color: white;
  border: none;
  padding: 12px 24px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  font-weight: bold;
}

.test-btn:hover, .clear-btn:hover {
  background: #06ad56;
}

.test-btn:disabled {
  background: #6c757d;
  cursor: not-allowed;
}

.clear-btn {
  background: #6c757d;
  margin-top: 10px;
}

.clear-btn:hover {
  background: #545b62;
}

.logs {
  background: #fff;
  border: 1px solid #ddd;
  border-radius: 4px;
  padding: 15px;
  max-height: 300px;
  overflow-y: auto;
  font-family: 'Courier New', monospace;
  font-size: 12px;
}

.log-entry {
  margin-bottom: 5px;
  padding: 2px 0;
  border-bottom: 1px solid #f0f0f0;
}

.log-entry:last-child {
  border-bottom: none;
}
</style>
