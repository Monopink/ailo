import { defineStore } from 'pinia'
import { ref } from 'vue'
import apiClient from '../services/api'
import { useToast } from 'vue-toastification'

const toast = useToast()

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)
  const token = ref(localStorage.getItem('token') || null)

  // Set the token in the API client's headers if it exists from the start
  if (token.value) {
    apiClient.defaults.headers.common['Authorization'] = `Bearer ${token.value}`
  }

  function setToken(newToken) {
    token.value = newToken
    if (newToken) {
      localStorage.setItem('token', newToken)
      apiClient.defaults.headers.common['Authorization'] = `Bearer ${newToken}`
    } else {
      localStorage.removeItem('token')
      delete apiClient.defaults.headers.common['Authorization']
    }
  }

  function setUser(newUser) {
    user.value = newUser
  }

  async function fetchUser() {
    if (!token.value) return
    try {
      const { data } = await apiClient.get('/auth/me')
      setUser(data)
    } catch (error) {
      console.error('Failed to fetch user:', error)
      logout()
    }
  }

  async function loginWithPassword(phone, password) {
    try {
      const response = await apiClient.post('/auth/login/password', { phone, password })
      const { access_token } = response.data
      setToken(access_token)
      await fetchUser()
    } catch (error) {
      if (error.response) {
        if (error.response.status === 401 || error.response.status === 400) {
          toast.error("手机号或密码错误")
        } else {
          toast.error(`系统错误: ${error.response.status}`)
        }
      } else if (error.request) {
        toast.error("网络错误，请检查您的连接")
      } else {
        toast.error("发生未知错误")
      }
      throw error
    }
  }

  async function login(access_token) {
    setToken(access_token)
    await fetchUser()
  }

  function logout() {
    setToken(null)
    setUser(null)
  }

  async function checkAuth() {
    console.log("Checking auth status...");
    if (token.value) {
      console.log("Token found, attempting to fetch user.");
      await fetchUser();
      if (user.value) {
        console.log("User fetched successfully:", user.value);
      } else {
        console.log("Failed to fetch user, user is null.");
      }
    } else {
      console.log("No token found.");
    }
  }

  return { user, token, loginWithPassword, login, logout, checkAuth, setToken, setUser }
}) 