/**
 * API service layer for application
 * Provides unified interface for all backend API calls
 */

import { createApiClient, createServiceClient, apiGet, apiPost } from '../utils/apiHelpers.js';
import { apiLogger } from '../utils/logger.js';
import { API_CONFIG } from '../config/constants.js';

// Log API configuration for debugging
apiLogger.info('API service initialized', {
  baseURL: API_CONFIG.BASE_URL,
  timeout: API_CONFIG.TIMEOUT,
});

// Create default API client
export const apiClient = createApiClient();

// Create specialized service clients
const contactsService = createServiceClient('CONTACTS');
const authService = createServiceClient('AUTH');

/**
 * Contact Management API
 */

/**
 * Get user's contact list
 */
export async function getContacts() {
  return contactsService.get('/api/v1/contacts', {
    operation: 'load_contacts',
  });
}

/**
 * Get specific contact's chat display information
 */
export async function getContactChatInfo(contactId) {
  if (!contactId) {
    throw new Error('Contact ID is required');
  }

  return contactsService.get(`/api/v1/contacts/${contactId}/chat-info`, {
    operation: 'load_chat',
  });
}

/**
 * Get user's contact limits and usage information
 */
export async function getContactLimits() {
  return contactsService.get('/api/v1/contacts/limits', {
    operation: 'load_contacts',
  });
}

/**
 * Search available contacts
 */
export async function searchContacts(query) {
  if (!query || query.trim().length === 0) {
    throw new Error('Search query is required');
  }

  const encodedQuery = encodeURIComponent(query.trim());
  return contactsService.get(`/api/v1/contacts/search?query=${encodedQuery}`, {
    operation: 'search_contacts',
  });
}

/**
 * Add a new contact
 */
export async function addContact(contactId) {
  if (!contactId) {
    throw new Error('Contact ID is required');
  }

  return contactsService.post('/api/v1/contacts/add',
    { contact_id: contactId },
    { operation: 'add_contact' }
  );
}

/**
 * Authentication API
 */

/**
 * Send SMS verification code
 */
export async function sendSmsCode(phone) {
  if (!phone) {
    throw new Error('Phone number is required');
  }

  return authService.post('/api/v1/auth/send-code',
    { phone },
    { operation: 'send_sms' }
  );
}

/**
 * User registration
 */
export async function register(phone, code, password) {
  if (!phone || !code || !password) {
    throw new Error('Phone, code, and password are required');
  }

  return authService.post('/api/v1/auth/register',
    { phone, code, password },
    { operation: 'register' }
  );
}

/**
 * User login
 */
export async function login(phone, password) {
  if (!phone || !password) {
    throw new Error('Phone and password are required');
  }

  return authService.post('/api/v1/auth/login',
    { phone, password },
    { operation: 'login' }
  );
}

/**
 * Get current user information
 */
export async function getCurrentUser() {
  return authService.get('/api/v1/auth/me', {
    operation: 'get_user_info',
  });
}

/**
 * Update user profile
 */
export async function updateProfile(profileData) {
  if (!profileData) {
    throw new Error('Profile data is required');
  }

  return authService.put('/api/v1/users/profile',
    profileData,
    { operation: 'update_profile' }
  );
}

/**
 * Legacy API functions for backward compatibility
 * These maintain the old function signatures but use new implementation
 */

// Legacy getContacts with token parameter (for existing code)
export const getContactsLegacy = (token) => {
  apiLogger.warn('Using legacy getContacts function, consider updating to new API');
  return getContacts();
};

// Export default API client for direct access if needed
export default apiClient;