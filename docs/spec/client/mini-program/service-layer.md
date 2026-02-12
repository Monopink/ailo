# Service 层架构规范

## 目的

封装数据获取、转换和业务逻辑，提供统一的数据访问接口。

## 核心约束

<critical-rules>
- 所有 API 数据获取必须通过 Service 层
- Service 负责将 API 返回的原始数据转换为 ViewModel
- **禁止在页面层直接调用 API 函数**（如 `utils/profile.ts`）
- **禁止在页面层手动构建 ViewModel**（如 `displayAvatar = getAvatarUrl(...)`）
</critical-rules>

## 缓存与并发控制规则

### 默认策略
- **默认禁止内存缓存**：MVP 阶段原则上不实现缓存，避免增加复杂度

### 允许缓存的例外场景

#### 1. 全局共享的用户资料（如 profileService）
- **理由**：多个页面共享同一数据，避免短时间内重复请求
- **要求**：必须有 TTL（1-5分钟）+ 强制刷新机制

#### 2. 防重复请求逻辑（loadingPromise）
- **理由**：避免并发请求导致的竞态条件（Race Condition）
- **要求**：请求完成后必须清空 Promise

#### 3. 其他业务数据
- **联系人列表、消息列表等仍禁止缓存**

### 缓存实现约束（仅适用于允许缓存的场景）

<critical-rules>
- 必须有明确的 TTL 机制（推荐 1-5 分钟）
- 必须支持强制刷新（forceRefresh 参数）
- 必须实现防重复请求（避免并发问题）
- 缓存逻辑必须封装在 Service 层，页面层不可见
- 必须有清晰的日志记录（cache hit/miss/refresh）
</critical-rules>

## 现有 Services

| Service | 职责 | 文件路径 |
|---------|------|----------|
| `profileService` | 用户资料管理（头像、昵称、性别等） | `utils/profile-service.ts` |
| `accountService` | 账号信息管理（手机号、邮箱等） | `utils/account-service.ts` |
| `contact-service` | 联系人管理 | `utils/contact-service.ts` |
| `auth-service` | 认证管理 | `utils/auth-service.ts` |
| `discovery-service` | 发现页管理 | `utils/discovery-service.ts` |

## 消息服务约束

- optimistic 消息必须携带 `msg_id_client`
- 时间线消息去重主键固定为 `msg_id_server`
- 收到 self echo 且命中 `(conv_id, msg_id_client)` 时，消息状态执行替换收敛到 `msg_id_server`
- `POST /api/v1/messages/ack` 的游标推进基于 `msg_id_server`

## 参考实现

查看以下文件了解标准实现模式：
- [utils/profile-service.ts](../../../frontend/wx-minipg/utils/profile-service.ts)
- [utils/account-service.ts](../../../frontend/wx-minipg/utils/account-service.ts)

## 例外场景

setup 页面（首次登录设置资料）可以直接调用 API，因为涉及特殊的初始化逻辑。

## 错误处理规范

### 用户层展示
- 严禁向用户暴露内部错误
- 显示友好的错误提示信息

### 开发者层记录
- 使用 `logger.error` 记录详细错误信息
- 包含完整的错误堆栈和上下文

### 回退值规范（WXML层）

| 场景 | 规范 | 示例 |
|------|------|------|
| 系统消息 | 允许回退值 | `{{errorMessage \|\| '操作失败'}}` |
| 资料数据 | 禁止回退值 | `{{nickname}}` |
| 绑定数据 | 在逻辑层处理 | `displayPhone: user.phone ? format(phone) : '未绑定'` |
