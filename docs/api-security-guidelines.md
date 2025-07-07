# API Security Guidelines

## Overview

This document outlines the security guidelines and best practices implemented in the Says application to protect user data and maintain system security.

## Database ID Protection

### Problem

Database internal IDs (auto-increment primary keys) should never be exposed to clients as they:

- Reveal internal system structure
- Can be used for enumeration attacks
- Provide no value to frontend applications
- Violate data privacy principles

### Solution

All API responses use `entity_id` (UUID-based) instead of database `id` fields.

#### Before (Insecure)

```json
{
  "id": 2,                    // ❌ Database internal ID exposed
  "entity_id": "u1002",
  "username": "li4",
  "email": "lisi@example.com"
}
```

#### After (Secure)

```json
{
  "entity_id": "u1002",       // ✅ Only public identifier
  "username": "li4",
  "email": "lisi@example.com",
  "status": "active",
  "role": "user"
}
```

### Implementation

#### accounts_service

**File**: `backend/accounts_service/app/schemas/user.py`

```python
# Properties to return to client
class User(UserBase):
    # id: int  # ❌ Removed - database ID should not be exposed
    entity_id: str
    status: str
    role: str
    is_verified: bool
    subscription_type: str
```

#### contacts_service

**File**: `backend/contacts_service/app/services/contacts_service.py`

```python
return {
    # "id": contact.id,  # ❌ Removed - database ID should not be exposed
    "entity_id": contact.contact_entity_id,
    "contact_type": contact.contact_type,
    "nickname": profile.nickname,
    "bio": profile.bio,
    # ... other fields
}
```

## Frontend Display Logic

### No Fallback Mechanism Policy

The application implements a strict "no fallback" policy for user interface display:

#### Problem

Traditional fallback mechanisms hide data availability issues:

```javascript
// ❌ Bad: Hides when nickname is not available
{{ user.nickname || user.username || user.phone }}
```

#### Solution

Explicit display without fallbacks:

```javascript
// ✅ Good: Only shows nickname, nothing if unavailable
{{ user.nickname }}
```

### Implementation

#### Frontend Display

**File**: `frontend/web/src/App.vue`

```vue
<template>
  <div class="welcome-message">
    {{ authStore.user.nickname }}  <!-- Only nickname, no fallback -->
  </div>
</template>
```

#### Data Fetching

**File**: `frontend/web/src/stores/auth.js`

```javascript
// Get user basic info from accounts_service
const { data } = await apiClient.get('/auth/me')

// Get social profile from contacts_service
try {
  const profileResponse = await axios.get(`/api/contacts/profile/${data.entity_id}`, {
    headers: {
      'Authorization': `Bearer ${token.value}`,
      'Content-Type': 'application/json'
    }
  })
  if (profileResponse.data.status === 'success') {
    data.nickname = profileResponse.data.data.nickname
  }
} catch (profileError) {
  // If social profile not found, leave nickname empty
  console.warn('Social profile not found, nickname will be empty')
  data.nickname = ''
}
```

## API Authentication

### Token-based Authentication

All API calls must include proper authentication tokens:

```javascript
// ✅ Correct: Manual token for cross-service calls
const profileResponse = await axios.get(`/api/contacts/profile/${entity_id}`, {
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  }
})

// ❌ Incorrect: Using apiClient for different service
const profileResponse = await apiClient.get(`/api/contacts/profile/${entity_id}`)
```

### Service Separation

- `accounts_service`: User authentication and basic info
- `contacts_service`: Social profiles and contact management
- `bot_message_service`: Message handling and bot interactions

Each service has its own authentication requirements and data scope.

## Data Flow Architecture

```
Frontend Request
    ↓
1. Get user basic info from accounts_service (/api/v1/auth/me)
    ↓
2. Get social profile from contacts_service (/api/v1/contacts/profile/{entity_id})
    ↓
3. Combine data in frontend store
    ↓
4. Display only nickname (no fallback)
```

## Security Checklist

### API Response Validation

- [ ] No database `id` fields in responses
- [ ] Only `entity_id` used for public identification
- [ ] Proper authentication tokens included
- [ ] Cross-service calls use correct endpoints

### Frontend Security

- [ ] No fallback display mechanisms
- [ ] Explicit error handling for missing data
- [ ] Proper token management for cross-service calls
- [ ] No sensitive data in console logs (production)

### Service Security

- [ ] Each service validates its own authentication
- [ ] Database IDs never exposed in API responses
- [ ] Proper CORS configuration
- [ ] Input validation on all endpoints

## Testing

### API Security Testing

```bash
# Test user API - should not contain database ID
curl -H "Authorization: Bearer $TOKEN" http://localhost:8001/api/v1/auth/me

# Test contacts API - should not contain database ID
curl -H "Authorization: Bearer $TOKEN" http://localhost:8002/api/v1/contacts
```

### Frontend Testing

1. Login to application
2. Check browser console for user object
3. Verify no `id` field in user data
4. Verify nickname displays correctly
5. Verify no fallback when nickname is empty

## Compliance

This implementation ensures:

- **Data Privacy**: Internal database structure is not exposed
- **Security**: No enumeration attacks possible via database IDs
- **User Experience**: Clear indication when data is not available
- **Maintainability**: Explicit data flow without hidden fallbacks
