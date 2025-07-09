# 前端安全规范

## 概述

本文档定义了Says应用前端的安全规范和最佳实践，确保用户数据安全和良好的用户体验。

## 显示逻辑规范

### 无回退机制原则

前端显示必须遵循"无回退机制"原则，即当数据不可用时，不显示任何内容，而不是显示替代数据。

#### ❌ 错误示例

```vue
<template>
  <!-- 错误：使用回退机制隐藏了数据不可用的问题 -->
  <div class="user-name">
    {{ user.nickname || user.username || user.phone }}
  </div>
</template>
```

#### ✅ 正确示例

```vue
<template>
  <!-- 正确：只显示nickname，如果不可用则不显示 -->
  <div class="user-name">
    {{ user.nickname }}
  </div>
</template>
```

### 数据获取策略

用户信息获取采用分层策略：

1. **基础信息**：从accounts_service获取用户基本信息
2. **社交档案**：从contacts_service获取nickname等社交信息
3. **前端组合**：在前端store中组合数据

#### 实现示例

```javascript
// stores/auth.js
async function fetchUser() {
  if (!token.value) return
  
  try {
    // 1. 获取用户基础信息
    const { data } = await apiClient.get('/auth/me')

    // 2. 获取社交档案
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
      // 如果社交档案不存在，nickname保持为空
      console.warn('Social profile not found, nickname will be empty')
      data.nickname = ''
    }

    setUser(data)
  } catch (error) {
    console.error('Failed to fetch user:', error)
    logout()
  }
}
```

## API调用规范

### 跨服务认证

不同服务的API调用需要使用不同的方式：

#### accounts_service API

```javascript
// 使用配置好的apiClient（自动包含认证）
const response = await apiClient.get('/auth/me')
```

#### contacts_service API

```javascript
// 使用原始axios并手动添加认证token
const response = await axios.get('/api/contacts/profile/u1002', {
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  }
})
```

### 错误处理

API调用失败时的处理策略：

```javascript
try {
  const response = await apiCall()
  // 处理成功响应
} catch (error) {
  if (error.response) {
    // 服务器响应错误
    console.error('API Error:', error.response.status, error.response.data)
  } else if (error.request) {
    // 网络错误
    console.error('Network Error:', error.request)
  } else {
    // 其他错误
    console.error('Error:', error.message)
  }
  // 不使用默认值，让错误状态明确显示
}
```

## 数据安全

### 敏感数据处理

1. **不缓存敏感数据**：认证token等敏感信息不应长期缓存
2. **清理用户数据**：登出时彻底清理所有用户相关数据
3. **验证数据完整性**：接收到的数据应进行基本验证

### 本地存储策略

```javascript
// 只存储必要的认证信息
localStorage.setItem('token', accessToken)

// 登出时清理所有数据
function logout() {
  localStorage.removeItem('token')
  setToken(null)
  setUser(null)
  // 清理其他相关状态
}
```

## 用户体验规范

### 加载状态

当数据不可用时，应明确显示加载状态而不是显示错误数据：

```vue
<template>
  <div class="user-info">
    <div v-if="loading" class="loading">加载中...</div>
    <div v-else-if="user.nickname" class="user-name">
      {{ user.nickname }}
    </div>
    <!-- 如果nickname不可用，不显示任何内容 -->
  </div>
</template>
```

### 错误提示

错误信息应该明确且有用：

```javascript
// 明确的错误提示
if (!user.nickname) {
  console.warn('用户昵称不可用，请检查社交档案设置')
}

// 避免误导性的默认值
// ❌ 错误：user.nickname = user.username || '用户'
// ✅ 正确：user.nickname = '' // 保持为空
```

## 开发调试

### 控制台日志

开发环境中的日志应该有助于调试：

```javascript
// 结构化日志
console.log('User fetched successfully:', {
  entity_id: user.entity_id,
  has_nickname: !!user.nickname,
  has_username: !!user.username
})

// 错误日志
console.error('Social profile fetch failed:', {
  entity_id: user.entity_id,
  error: error.message,
  status: error.response?.status
})
```

### 数据验证

在开发环境中验证数据完整性：

```javascript
function validateUserData(user) {
  if (process.env.NODE_ENV === 'development') {
    if (user.id) {
      console.error('⚠️ 安全警告：用户数据包含数据库ID', user)
    }
    if (!user.entity_id) {
      console.error('⚠️ 数据错误：缺少entity_id', user)
    }
  }
}
```

## 安全检查清单

### 代码审查清单

- [ ] 没有使用回退显示机制（`||` 操作符用于显示）
- [ ] API调用包含正确的认证信息
- [ ] 错误处理不使用默认值
- [ ] 敏感数据正确清理
- [ ] 用户数据不包含数据库ID
- [ ] 跨服务API调用使用正确的方式

### 测试清单

- [ ] 登录后顶部显示正确的nickname
- [ ] nickname不可用时不显示任何内容
- [ ] 浏览器控制台中用户对象不包含数据库ID
- [ ] 登出后所有用户数据被清理
- [ ] API错误时不显示错误的默认值

## 相关文档

- [API安全指南](../api-security-guidelines.md)
- [开发指南](../development-guide-zh.md)
- [测试功能文档](../test_functionality.md)
