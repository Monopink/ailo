// Common utility functions

/**
 * Check if value is null, undefined, or empty string
 */
export function isNullOrWhitespace(value) {
  return value === null || value === undefined || value === '' || (typeof value === 'string' && value.trim() === '')
}

/**
 * Check if value is null or undefined
 */
export function isNullOrUndef(value) {
  return value === null || value === undefined
}

/**
 * Format date to readable string
 */
export function formatDate(date, format = 'YYYY-MM-DD HH:mm:ss') {
  if (!date) return ''

  const d = new Date(date)
  if (isNaN(d.getTime())) return ''

  const year = d.getFullYear()
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  const hours = String(d.getHours()).padStart(2, '0')
  const minutes = String(d.getMinutes()).padStart(2, '0')
  const seconds = String(d.getSeconds()).padStart(2, '0')

  return format
    .replace('YYYY', year)
    .replace('MM', month)
    .replace('DD', day)
    .replace('HH', hours)
    .replace('mm', minutes)
    .replace('ss', seconds)
}

/**
 * Debounce function
 */
export function debounce(func, wait) {
  let timeout
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout)
      func(...args)
    }
    clearTimeout(timeout)
    timeout = setTimeout(later, wait)
  }
}

/**
 * Simple notification function
 */
export function showMessage(message, type = 'info') {
  // Simple console logging for now - can be enhanced later
  console.log(`[${type.toUpperCase()}] ${message}`)

  // Simple alert for user feedback
  if (type === 'error') {
    alert(`Error: ${message}`)
  }
}

/**
 * Use resize observer
 */
export function useResize(element, callback) {
  if (!window.ResizeObserver) return null

  const observer = new ResizeObserver(callback)
  observer.observe(element)
  return observer
}
