// Version management for cache busting
const APP_VERSION = import.meta.env.VITE_APP_VERSION || '1.0.0'
const VERSION_CHECK_INTERVAL = 10000 // Check every 10 seconds for faster updates

let versionCheckInterval = null

// Get current app version
export function getCurrentVersion() {
  return APP_VERSION
}

// Check if a new version is available
export async function checkForUpdates() {
  try {
    const response = await fetch('/version.json?' + Date.now(), {
      cache: 'no-cache'
    })

    if (!response.ok) {
      console.warn('Failed to check for updates')
      return false
    }

    const data = await response.json()
    const serverVersion = data.version

    console.log(`Current version: ${APP_VERSION}, Server version: ${serverVersion}`)

    if (serverVersion !== APP_VERSION) {
      console.log('New version available, reloading...')
      return true
    }

    return false
  } catch (error) {
    console.warn('Error checking for updates:', error)
    return false
  }
}

// Start automatic version checking
export function startVersionCheck() {
  if (versionCheckInterval) {
    return // Already started
  }

  console.log('Starting automatic version check...')

  versionCheckInterval = setInterval(async () => {
    const hasUpdate = await checkForUpdates()
    if (hasUpdate) {
      // Auto-reload without user confirmation for seamless updates
      console.log('🔄 New version detected, auto-reloading...')
      forceReload()
    }
  }, VERSION_CHECK_INTERVAL)
}

// Stop automatic version checking
export function stopVersionCheck() {
  if (versionCheckInterval) {
    clearInterval(versionCheckInterval)
    versionCheckInterval = null
    console.log('Stopped automatic version check')
  }
}

// Force reload with cache clearing
export function forceReload() {
  // Clear all caches
  if ('caches' in window) {
    caches.keys().then(names => {
      names.forEach(name => {
        caches.delete(name)
      })
    })
  }

  // Clear localStorage version info
  localStorage.removeItem('app_version')

  // Reload with cache busting
  window.location.href = window.location.href.split('?')[0] + '?v=' + Date.now()
}

// Initialize version management
export function initVersionManagement() {
  // Store current version
  localStorage.setItem('app_version', APP_VERSION)

  // Only start version checking in production to avoid development issues
  if (import.meta.env.PROD) {
    startVersionCheck()
    console.log(`App version ${APP_VERSION} initialized with auto-refresh`)
  } else {
    console.log(`App version ${APP_VERSION} initialized (dev mode, no auto-refresh)`)
  }
}
