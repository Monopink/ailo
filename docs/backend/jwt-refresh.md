# JWT Token 刷新机制 (MVP版本)

## 概述

为MVP阶段设计的简单、高性价比的JWT token刷新方案，平衡了安全性和开发复杂度。

## 设计原则

### MVP阶段优先级

1. **简单实现** - 避免复杂的refresh token机制
2. **安全基础** - 保证基本的token安全性
3. **用户体验** - 避免频繁登录中断
4. **易于维护** - 代码简洁，便于后续扩展

## 实现方案

### 1. 简单刷新端点

**端点**: `POST /api/v1/auth/refresh`

**功能**:

- 验证当前token有效性
- 生成新的token（延长过期时间）
- 返回新token给客户端

**使用方式**:

```javascript
// 前端调用示例
const response = await fetch('/api/v1/auth/refresh', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${currentToken}`,
    'Content-Type': 'application/json'
  }
});

const { access_token } = await response.json();
// 更新本地存储的token
localStorage.setItem('token', access_token);
```

### 2. 自动刷新策略

**前端实现建议**:

```javascript
// 在API请求拦截器中检查token过期
axios.interceptors.response.use(
  response => response,
  async error => {
    if (error.response?.status === 401) {
      try {
        // 尝试刷新token
        const refreshResponse = await refreshToken();
        const newToken = refreshResponse.data.access_token;
        
        // 更新token并重试原请求
        localStorage.setItem('token', newToken);
        error.config.headers.Authorization = `Bearer ${newToken}`;
        return axios.request(error.config);
      } catch (refreshError) {
        // 刷新失败，跳转到登录页
        redirectToLogin();
      }
    }
    return Promise.reject(error);
  }
);
```

### 3. 主动刷新策略

**后端工具函数**:

```python
# 在backend/app/core/security.py中已实现
def is_token_near_expiry(token: str, threshold_minutes: int = 60) -> bool:
    """检查token是否即将过期"""
    
def refresh_token_if_needed(token: str, entity_id: str) -> Optional[str]:
    """如需要则刷新token"""
```

**前端主动检查**:

```javascript
// 定期检查token是否需要刷新（可选）
setInterval(async () => {
  const token = localStorage.getItem('token');
  if (token && isTokenNearExpiry(token)) {
    try {
      await refreshToken();
    } catch (error) {
      console.warn('Token refresh failed:', error);
    }
  }
}, 5 * 60 * 1000); // 每5分钟检查一次
```

## 配置参数

### Token过期时间

```python
# backend/app/core/config.py
ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8天 (MVP阶段较长)
```

### 刷新阈值

```python
# 默认在token过期前1小时触发刷新
threshold_minutes = 60
```

## 安全考虑

### MVP阶段的安全措施

1. **HTTPS强制** - 生产环境必须使用HTTPS
2. **Token验证** - 每次刷新都验证当前token有效性
3. **用户验证** - 确保用户仍然存在且状态正常
4. **日志记录** - 记录所有刷新操作便于审计

### 暂不实现的复杂功能

- Refresh Token机制（后续版本考虑）
- Token黑名单（MVP阶段不需要）
- 多设备Token管理（当前限制一设备一类型）

## 使用指南

### 前端集成步骤

1. **安装拦截器**

```javascript
// 在main.js或api配置文件中
import { setupTokenRefresh } from './utils/tokenRefresh';
setupTokenRefresh();
```

2. **处理刷新响应**

```javascript
// 成功刷新后更新本地token
const handleTokenRefresh = (newToken) => {
  localStorage.setItem('token', newToken);
  // 可选：通知其他组件token已更新
  eventBus.emit('tokenRefreshed', newToken);
};
```

3. **错误处理**

```javascript
// 刷新失败时的处理
const handleRefreshFailure = () => {
  localStorage.removeItem('token');
  router.push('/login');
  showMessage('登录已过期，请重新登录');
};
```

### 后端监控

**关键日志事件**:

- `token_refreshed` - 成功刷新
- `token_refresh_error` - 刷新失败
- `token_expiry_check_error` - 过期检查错误

**监控指标**:

```bash
# 刷新频率监控
grep "token_refreshed" /app/logs/service.log | wc -l

# 刷新失败率
grep "token_refresh_error" /app/logs/service.log | wc -l
```

## 后续扩展计划

### 版本2.0考虑的功能

1. **Refresh Token** - 独立的刷新token机制
2. **Token撤销** - 支持主动撤销token
3. **设备管理** - 多设备token管理
4. **滑动过期** - 基于活跃度的动态过期

### 迁移路径

当前MVP方案设计时考虑了向后兼容，后续升级时：

1. 保持现有刷新端点兼容
2. 逐步引入refresh token
3. 客户端可选择使用新机制

## 最佳实践

### 开发环境

- Token过期时间可以设置较短便于测试
- 开启详细的刷新日志

### 生产环境

- 使用较长的token过期时间减少刷新频率
- 监控刷新失败率和频率
- 设置合理的刷新阈值

### 用户体验

- 静默刷新，用户无感知
- 刷新失败时友好提示
- 避免在用户操作过程中强制登录

## 故障排查

### 常见问题

**1. 刷新循环**

```
原因: 新token立即被认为过期
解决: 检查服务器时间同步
```

**2. 刷新失败**

```
原因: 用户状态变更或token格式错误
解决: 检查用户状态和token解析逻辑
```

**3. 前端token不更新**

```
原因: 拦截器配置错误
解决: 确保正确更新localStorage和请求头
```

这个MVP方案在保证基本安全性的同时，实现简单、维护成本低，适合快速迭代的开发阶段。
