# 头像上传前端设计文档

## 1. 目标
- 在 `pages/setup/setup` 与 `pages/profile-detail/profile-detail` 中提供统一的头像选择、裁剪与上传体验，提升注册和资料维护的完成率。
- 通过后端代理接口 `/api/v1/media/upload` 完成所有上传，彻底屏蔽对象存储细节，确保安全性与后续可迁移性。
- 复用现有裁剪页 (`pages/avatar-cropper`) 与媒体工具函数，保持实现精简、职责明确、易于维护。
- 为所有失败场景提供可预期的校验与提示，禁止静默失败，便于排查问题。

## 2. 约束
- **后端代理上传**：微信小程序无法自由设置 `Content-Length` 等 Header，且会对带签名的 Query 进行裁剪，导致直传 COS 出现 `403 SignatureDoesNotMatch`。因此客户端必须将文件通过 `/api/v1/media/upload` 代理到对象存储。
- **文件规格**：裁剪输出固定为 512x512 WebP，质量 85%。后端仅接受 JPEG/PNG/WebP，单文件不超过 2MB，且 `file_type` 必须为 1（avatar）。
- **配额限制**：头像每日上传次数 5 次、总量 10MB，由后端返回 429 错误并提示用户。
- **认证依赖**：上传接口需要 Bearer Token，所有操作必须在身份态可用后执行。
- **后端兜底**：Setup 页面允许用户跳过头像上传。登录完成后所有资料接口都会返回最终可展示的头像（或后端默认占位），前端不再打包和维护任何默认头像资源。

## 3. 用户体验流程
### 3.1 Setup 页面
1. 页面顶部展示当前本地头像状态（首次为空时展示 Avatar 组件自带的占位样式，无需手工兜底）。
2. 用户点击头像区域后，调用 `completeAvatarUpload()` 触发选择 → 裁剪 → 上传。
3. 上传成功后，将 `{ avatarFileId, avatarUrl }` 写入本地数据，并弹出成功提示。
4. 继续填写昵称、性别等必填项。
5. 通过 `updateUserProfile`（PUT `/api/v1/user/profile`）提交资料，存在 `avatarFileId` 时映射为 `avatar_file_id`，提交成功后刷新用户缓存并跳回首页。
6. 沿用既有完成流程与跳转逻辑。

### 3.2 Profile Detail 页面
1. 使用 `profile.displayAvatar` 显示当前头像。
2. 点击头像同样调用 `completeAvatarUpload()`。
3. 获得 `{ fileId, url }` 后，调用 `updateUserAvatar(fileId)`（封装自 `PUT /api/v1/user/profile`）。
4. 成功后刷新资料并提示“更新成功”；失败则保持旧头像并展示错误文案。

### 3.3 技术序列
1. `wx.chooseMedia`：用户拍照或从相册选择单张图片。
2. `pages/avatar-cropper`：通过 `wx.navigateTo` + `EventChannel` 裁剪输出 512x512 WebP。
3. `wx.getFileInfo`：获取裁剪结果的大小（必要时可计算 hash）。
4. `/api/v1/media/upload`：以 `multipart/form-data` 提交 `file`、`file_type=1`、`mime_type`、`file_size` 等字段，由后端完成上传。
5. 后端处理：校验配额与格式，写入对象存储，激活 `media_files` 记录，返回 `{ file_id, url }`。
6. 资料更新：在需要时调用 `PUT /api/v1/user/profile` 绑定 `avatar_file_id`，并刷新前端状态。

### 3.4 Setup 路由控制
1. Auth/登录接口返回 `needs_profile_setup`，登录成功后由 `authService` 保存该标记。
2. App 初始化或页面 onShow 时检测该标记：true → `wx.redirectTo('/pages/setup/setup')`；false → 进入原页面。
3. Setup 页面加载时若标记为 false（例如用户手动返回），立即 `wx.switchTab` 到首页。
4. 完成资料更新后调用 `authService.markProfileSetupComplete()` 将标记置 false 并刷新 `/users/profile` 缓存。

## 4. 架构与模块
### 4.1 模块职责
| 模块 | 职责 | 说明 |
| --- | --- | --- |
| `utils/avatar-uploader.ts`（新增） | 串联选择 → 裁剪 → 上传，对外暴露 `selectAndCropAvatar`、`uploadAvatarToBackend`、`completeAvatarUpload`。 | 统一处理 loading、错误转换、Promise 返回 `{ fileId, url }`。 |
| `utils/media.ts` | 封装 `/api/v1/media/upload` 请求与响应校验。 | 确保接口异常以统一错误对象抛出。 |
| `utils/profile.ts` | 新增 `updateUserAvatar(fileId: string)`，封装 `PUT /api/v1/user/profile`。 | 集中管理资料相关 API，便于复用。 |
| `pages/avatar-cropper/*` | 输出确定性的 512x512 WebP。 | 通过 EventChannel 与调用方通信。 |
| `pages/setup/setup.ts` | 维护临时头像状态、处理点击与提交逻辑。 | 上传时展示 loading，避免重复点击。 |
| `pages/profile-detail/profile-detail.ts` | 提供 `editAvatar()` 调用上传流程并刷新数据。 | 通过布尔标记阻止并发上传请求。 |
| `utils/avatar.ts` | 根据 `fileId` 或 URL 生成展示地址（不再主动兜底到本地资源）。 | 用于所有头像组件保持一致性，由后端决定默认头像。 |

### 4.2 状态与并发控制
- 页面 `data` 中维护 `avatarFileId`、`avatarUrl`、`uploadingAvatar`。
- 当 `uploadingAvatar` 为 true 时禁用再次点击，防止重复请求。
- 离开页面或流程终止时重置状态，避免残留 loading。

## 5. 接口与数据映射
### 5.1 `POST /api/v1/media/upload`
- **请求**：`multipart/form-data`，字段见 `docs/api/media.md`。头像上传需提供 `file_type=1`、`mime_type='image/webp'`、`file_size`，可选 `file_hash`、`original_name`。
- **响应**：`{ "file_id", "url", "duplicate" }`。若 `duplicate=true` 表示命中去重，直接复用返回 URL。
- **前端处理**：解析 JSON，校验 `file_id` 与 `url`，更新状态；4xx 错误直接提示用户，不做自动重试。

### 5.2 `PUT /api/v1/user/profile`
- 仅在上传成功后包含 `avatar_file_id` 字段，避免覆盖已有头像。
- 后端响应会携带最新头像 URL，应优先使用返回值更新界面，减少额外查询。

### 5.3 数据辅助方法
- `buildRegistrationPayload(data)`：在存在 `avatarFileId` 时注入 `avatar_file_id`。
- `getAvatarUrl(fileIdOrUrl)`：保证 setup 与 profile 页面展示一致性。

## 6. 错误处理与用户提示
| 场景 | 后端 detail / 错误 | 前端反馈 |
| --- | --- | --- |
| 用户取消选择/裁剪 | `errMsg` 含 `cancel` | 静默结束，保持原头像。 |
| 文件大于 2MB | HTTP 413 | `wx.showToast({ title: '图片过大（最大2MB）', icon: 'none' })`。 |
| 不支持的格式 | HTTP 415 | `wx.showToast({ title: '图片格式不支持', icon: 'none' })`。 |
| 超出配额 | HTTP 429 | `wx.showToast({ title: '今日上传次数已用完', icon: 'none' })`。 |
| 网络/上传失败 | `wx.uploadFile` fail | `wx.showToast({ title: '上传失败，请检查网络', icon: 'none' })`，同时记录日志。 |
| 后端校验失败 | HTTP 400 + detail | 展示 detail，如缺失则提示“上传失败，请重试”。 |
| 身份失效 | HTTP 401 | 触发全局重新登录，再重试上传。 |

- 所有流程在 `finally` 中调用 `wx.hideLoading()` 并重置 `uploadingAvatar`。
- 上传失败时保留后端已确认的旧头像，避免空白状态。

## 7. 日志与监控
- 使用 `utils/logger` 记录 `logger.info('[avatar] upload start', { page, sourceType })` 与 `logger.error('[avatar] upload fail', { code, detail })`。
- 对 `completeAvatarUpload()` 执行时间做性能采样，洞察慢设备表现。
- 当后端返回 `duplicate=true` 时以 debug 级别记录，协助评估去重命中率。

## 8. 测试检查表
- [ ] iOS 与 Android 真机均可在 setup、profile 页面成功上传。
- [ ] 取消选择或裁剪后，界面无残留 loading。
- [ ] 快速连续点击只会保留最后一次上传，且不会并发发起多个请求。
- [ ] 常见错误（413/415/429/网络）均显示正确提示并允许用户重试。
- [ ] Setup 提交仅在存在 `avatar_file_id` 时携带该字段；缺省时仍可成功更新资料并跳回首页。
- [ ] Profile 页面在更新成功后立即刷新头像（验证缓存穿透策略）。

## 9. 后续优化方向
1. 在端内计算 SHA-256（如引入 `js-sha256`），命中后端秒传。
2. 基于 `wx.uploadFile.onProgressUpdate` 提供上传进度展示，待明确交互需求后实现。
3. 新增“移除头像”功能，允许用户回退到后端提供的默认头像（清空 avatar_file_id 即可触发后端兜底）。
4. 支持离线排队：在无网环境中保存裁剪结果，恢复网络后自动上传。
