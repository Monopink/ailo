import { request, authRequest } from '@/utils'

export default {
  // Authentication
  login: (data) => authRequest.post('/access_token', data, { noNeedToken: true }),
  getUserInfo: () => request.get('/userinfo'),
  getUserMenu: () => request.get('/base/usermenu'),
  getUserApi: () => request.get('/base/userapi'),
  // Profile
  updatePassword: (data = {}) => request.post('/base/update_password', data),

  // Admin Users Management
  getUserList: (params = {}) => request.get('/users/list', { params }),
  getUserById: (params = {}) => request.get('/users/get', { params }),
  createUser: (data = {}) => request.post('/users/create', data),
  updateUser: (data = {}) => request.post('/users/update', data),
  deleteUser: (params = {}) => request.delete('/users/delete', { params }),
  resetPassword: (data = {}) => request.post('/users/reset_password', data),



  // Audit Log (simplified)
  getAuditLogList: (params = {}) => request.get('/auditlog/list', { params }),
}
