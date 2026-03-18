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

## 页面 Service 层

- 位置：`frontend/mp-weixin/services/pages/*`
- 页面层调用页面 Service
- 页面 Service 负责页面级编排，组合领域 Service 与存储
- 页面 Service 覆盖页面：`login`、`chat`、`contact-info`、`field-edit`、`chat-detail`、`setup`、`account-security`、`profile`、`profile-detail`、`stranger-info`、`legal-document`、`index`、`square`、`contact-requests`

### 页面 Service 责任

- 构造最小可用模型（bootstrap）
- 执行一次性远程加载（load）
- 输出 `screenModel`、`refreshState` 与页面 ViewModel
- 统一错误语义分类与降级决策
- 处理并发控制与过期结果丢弃
- 处理入口页面传递的一次性消费数据（仅当前跳转有效）

### 页面层责任

- 绑定 `screenModel` 与 ViewModel
- 触发用户动作
- 处理鉴权失效 modal 与登录跳转

## 页面加载策略

- 页面远程加载在 `onLoad` 执行一次
- `onShow` 默认不触发远程加载
- `contact-info` 页面在 `onShow` 允许条件远程刷新：仅在 dirty 标记命中、TTL 过期或应用回到前台且 TTL 过期时触发
- 默认不做自动重试
- 一级页面（Tab 页）在 blank 失败场景执行有上限自动重试
- 一级页面自动重试为静默行为，不输出重试提示文案，不弹 toast
- 非一级页面可通过退出重进触发下一次加载
- `square` 在进入页面时刷新

## 缓存与并发控制规则

### 默认策略
- **默认禁止内存缓存**：原则上不新增内存缓存，避免增加复杂度

### 允许缓存的例外场景

#### 1. 全局共享的用户资料（如 profileService）
- **理由**：多个页面共享同一数据，避免短时间内重复请求
- **要求**：必须有 TTL（1-5分钟）+ 强制刷新机制

#### 2. 防重复请求逻辑（loadingPromise）
- **理由**：避免并发请求导致的竞态条件（Race Condition）
- **要求**：请求完成后必须清空 Promise

#### 3. 其他业务数据
- 联系人列表、消息列表不新增内存缓存，数据来源为本地持久化存储
- `stranger-info` 入口数据不落地存储，不设置 TTL

### 缓存实现约束（仅适用于允许缓存的场景）

<critical-rules>
- 必须有明确的 TTL 机制（推荐 1-5 分钟）
- 必须支持强制刷新（forceRefresh 参数）
- 必须实现防重复请求（避免并发问题）
- 缓存逻辑必须封装在 Service 层，页面层不可见
- 必须有清晰的日志记录（cache hit/miss/refresh）
</critical-rules>

## 页面状态输出

- 页面 Service 输出 `screenModel` 作为页面状态来源
- `screenModel` 与 `refreshState` 用于页面展示
- `contentVariant=empty` 仅表示业务结果为空
- `contentVariant=empty` 仅允许内容区内联展示，不允许整页替换
- 非业务空结果（网络失败、鉴权失败、参数错误、资源不存在）不得映射为 `empty`
- 最小可用模型已构造时，失败场景保留内容并设置 `refreshState=degraded`
- 最小可用模型未构造时，页面进入 `ready + blank`
- 一级页面在 `ready + blank` 时必须触发有上限自动重试（`legal-document` 除外）
- `legal-document` 失败保持 `ready + blank` 且不显示 toast

## 现有 Services

| Service | 职责 | 文件路径 |
|---------|------|----------|
| `profileService` | 用户资料管理（头像、昵称、性别等） | `utils/profile-service.ts` |
| `accountService` | 账号信息管理（手机号、邮箱等） | `utils/account-service.ts` |
| `contact-service` | 联系人管理 | `utils/contact-service.ts` |
| `auth-service` | 认证管理 | `utils/auth-service.ts` |
| `discovery-service` | 发现页管理 | `utils/discovery-service.ts` |

## 错误语义与分类

- 分类来源：`docs/api/error-codes.md` 与对应接口文档
- 前端分支依赖 `error_code`、`reason`、HTTP 状态码与微信请求错误语义
- 分类结果用于 Service 内部决策与日志
- 分类器位置：`frontend/mp-weixin/utils/error-classifier.ts`

### 分类语义

- `auth-invalid`
- `invalid-route`
- `not-found`
- `network-timeout`
- `network-offline`
- `server-error`
- `rate-limit`
- `refresh-failed`
- `partial-data-unavailable`
- `unknown`
- `not-found` 在最小可用模型已构造时按 `degraded` 处理

## 并发控制

- 页面 Service 维护请求序列号，保证 latest wins
- `bootstrap()` 需要 in-flight 去重
- `load()` 结果过期时不得覆盖最新状态
- 页面 `onUnload` 后，Service 必须停止向页面写入状态

## 消息服务约束

- optimistic 消息必须携带 `msg_id_client`
- 时间线消息去重主键固定为 `msg_id_server`
- 收到 self echo 且命中 `(conv_id, msg_id_client)` 时，消息状态执行替换收敛到 `msg_id_server`
- `POST /api/v1/messages/ack` 的游标推进基于 `msg_id_server`

## 参考实现

查看以下文件了解标准实现模式：
- [utils/profile-service.ts](../../../frontend/mp-weixin/utils/profile-service.ts)
- [utils/account-service.ts](../../../frontend/mp-weixin/utils/account-service.ts)

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
