import { defineStore } from 'pinia'
import { ref } from 'vue'
import { apiClient } from '../utils/apiHelpers'
import axios from 'axios'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)
  const token = ref(localStorage.getItem('token') || null)
  const needsProfileSetup = ref(false)

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

      // Try to get social profile for nickname and other profile data
      try {
        // Use axios with manual token for contacts API (goes through Vite proxy)
        const profileResponse = await axios.get(`/api/v1/contacts/profile/${data.id}`, {
          headers: {
            'Authorization': `Bearer ${token.value}`,
            'Content-Type': 'application/json'
          }
        })
        if (profileResponse.data.status === 'success') {
          const profileData = profileResponse.data.data
          data.nickname = profileData.nickname
          data.gender = profileData.gender
          data.bio = profileData.bio
          data.birth_date = profileData.birth_date
          data.location = profileData.location
          data.avatar_url = profileData.avatar_url
          needsProfileSetup.value = false
        }
      } catch (profileError) {
        // If social profile not found, user needs to set up profile
        console.warn('Social profile not found, user needs to set up profile')
        data.nickname = ''
        data.gender = null
        data.bio = null
        data.birth_date = null
        data.location = null
        data.avatar_url = null
        needsProfileSetup.value = true
      }

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

  async function createProfile(profileData) {
    try {
      const response = await axios.post('/api/v1/contacts/profile/me', profileData, {
        headers: {
          'Authorization': `Bearer ${token.value}`,
          'Content-Type': 'application/json'
        }
      })

      if (response.data.status === 'success') {
        // Update user data with new profile
        const profileData = response.data.data
        user.value.nickname = profileData.nickname
        user.value.gender = profileData.gender
        user.value.bio = profileData.bio
        user.value.birth_date = profileData.birth_date
        user.value.location = profileData.location
        user.value.avatar_url = profileData.avatar_url
        needsProfileSetup.value = false
        return response.data
      }
    } catch (error) {
      console.error('Failed to create profile:', error)
      throw error
    }
  }

  async function updateProfile(profileData) {
    try {
      const response = await axios.put('/api/v1/contacts/profile/me', profileData, {
        headers: {
          'Authorization': `Bearer ${token.value}`,
          'Content-Type': 'application/json'
        }
      })

      if (response.data.status === 'success') {
        // Update user data with updated profile
        const profileData = response.data.data
        user.value.nickname = profileData.nickname
        user.value.gender = profileData.gender
        user.value.bio = profileData.bio
        user.value.birth_date = profileData.birth_date
        user.value.location = profileData.location
        user.value.avatar_url = profileData.avatar_url
        return response.data
      }
    } catch (error) {
      console.error('Failed to update profile:', error)
      throw error
    }
  }

  return {
    user,
    token,
    needsProfileSetup,
    loginWithPassword,
    login,
    logout,
    checkAuth,
    setToken,
    setUser,
    createProfile,
    updateProfile
  }
}) 