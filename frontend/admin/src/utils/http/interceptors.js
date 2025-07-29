// Simple token management
function getToken() {
  return localStorage.getItem('admin_token')
}

export function reqResolve(config) {
  // Skip token for login requests
  if (config.noNeedToken) {
    return config
  }

  const token = getToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }

  return config
}

export function reqReject(error) {
  console.error('Request error:', error)
  return Promise.reject(error)
}

export function resResolve(response) {
  // Handle successful responses
  const { data } = response

  // Backend success format: {code: 200, msg: "OK", data: {...}}
  if (data?.code === 200) {
    return Promise.resolve(data)
  }

  // Handle error responses
  console.error('Response error:', data)
  return Promise.reject(data)
}

export async function resReject(error) {
  console.error('Response error:', error)

  // Handle 401 - redirect to login
  if (error.response?.status === 401) {
    localStorage.removeItem('admin_token')
    window.location.href = '/login'
    return
  }

  return Promise.reject(error)
}
