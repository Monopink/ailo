# Avatar Single Source of Truth (Mini Program)

## 状态
- Phase: 实施中（Approved）

## 执行摘要
**问题**：用户更新头像后，profile 页面显示新头像，chat 页面仍显示旧头像。

**根因**：当前用户资料存在多个来源：
- `STORAGE_KEYS.USER_INFO`（StoredAuthUser）被 chat 页面读取头像
- `/user/profile` 返回的 UserProfile 被 profile 页面读取头像
更新头像只刷新 profile 数据，未更新本地缓存，导致数据源不一致。

**最终方案**：
- 以 `profileService` 为唯一资料源（内存缓存 + TTL），所有页面只从 `profileService` 读取头像
- 删除 `StoredAuthUser` 中的 `avatar`/`nickname` 字段，禁止 fallback
- 头像更新后强制刷新 `profileService` 缓存

---

## 一、事实核实（已确认）
- `pages/chat/chat.ts` 在 `onLoad` 从 `getUserInfo()` 读取 `userInfo.avatar`。
- `pages/profile-detail/profile-detail.ts` 更新头像只调用 `updateUserAvatar()`，未同步更新本地用户缓存。
- `auth-service.ts` 登录时写入 `STORAGE_KEYS.USER_INFO`。
- `message-state-store.ts`、`message/service.ts`、`typing-manager.ts` 等模块依赖 `getUserInfo().qiao_id`。
- `storage.ts` 以 `qiao_id` 做多账号隔离，`buildUserKey()` 为关键路径。

---

## 二、硬性规则（无向后兼容）
1) **单一来源**：所有使用用户资料的页面/组件只读 `profileService` 的 `ProfileViewModel`（包含 `pages/profile/profile`、`pages/chat/chat`、会话列表、消息气泡、任意个人信息展示）。
2) **禁止 fallback（逻辑层）**：逻辑代码不得使用默认值/回退值隐藏错误。
3) **前端交互层体验要求**：交互层应避免报错/中断体验，允许在 UI 渲染中保留旧头像并静默重试，不弹窗打扰用户。
4) **头像更新强制刷新**：更新成功后必须 `await profileService.loadProfile(true)`，刷新内存缓存与 UI。
5) **登录预加载**：登录后触发 `profileService.loadProfile()`，失败不阻塞登录，但所有页面头像渲染必须依赖 `profileService` 结果。
6) **登出清理**：logout 必须 `profileService.clearProfile()`。
7) **移除过时字段**：`StoredAuthUser` 仅保留 `qiao_id`；删除 `avatar`/`nickname` 字段，不保留 deprecated。
8) **自动重试**：头像为空或加载失败时静默重试（不弹窗、不阻塞）。

---

## 三、最终架构方案

### 3.1 核心设计
- 不使用订阅机制（避免小程序生命周期导致的订阅清理问题）。
- 使用“拉取 + 内存缓存（TTL）”模式：页面 `onShow` 主动 `loadProfile()`。
- `profileService` 作为唯一资料读取入口。
- 失败不阻塞登录，但 UI 只显示 `profileService` 的结果；头像为空则保留旧头像并自动重试。
- 同一时间只允许一个 in-flight 的 profile 拉取，避免并发重复请求。

### 3.2 ProfileService 增强（不新增 store）
**文件**：`frontend/wx-minipg/utils/profile-service.ts`

新增/调整能力：
- `getProfile(): ProfileViewModel | null` 同步读取缓存
- `loadProfile(forceRefresh = false)` 负责拉取并刷新缓存
- `updateProfile()` 更新后同步刷新缓存
- `clearProfile()` 清除缓存
- 内存缓存 TTL：**3 分钟**（可调）
- **缓存结构**：
  - `cache: ProfileViewModel | null`
  - `cacheTime: number | null`
  - `loadPromise: Promise<ProfileViewModel> | null`
- **并发去重**：同一时间只允许一个 `loadProfile()` 请求，后续等待同一 Promise
- **错误处理**：
  - 逻辑层不返回默认值/回退值
  - 交互层允许继续展示旧头像，并由 `profileService` 静默重试

注意：不暴露 `setProfile()`；缓存更新只在 `loadProfile/updateProfile` 内部完成。

### 3.3 自动重试策略（需实现）
- 失败或头像为空时，使用**非阻塞**重试，不影响页面进入与其他流程。
- UI 允许继续显示旧头像（仅限交互层表现），逻辑层不得以回退值掩盖失败原因。
- 推荐策略：最多 3 次（立即 + 2s + 5s），成功即停止；超限后保留旧头像并等待用户下次进入页面触发。
- **取消机制**：当页面卸载或用户登出时，终止后续重试计时器。
- 仅 `profileService` 负责重试与节流，页面不得自行实现多套重试逻辑。

### 3.4 头像场景区分（需明确）
- **当前用户头像**：仅来自 `profileService`。
- **对方联系人头像**：继续使用 `contact.profile.avatar_url`（不修改）。
- 会话列表一般不展示当前用户头像，若未来新增此展示，必须走 `profileService`。

---

## 四、实施计划（无歧义）

### Phase 1: ProfileService
1. 修改 `frontend/wx-minipg/utils/profile-service.ts`
   - 加入内存缓存（`cache`、`cacheTime`、`TTL=3min`）
   - `getProfile()` 只读缓存，过期则返回 null
   - `loadProfile(forceRefresh)` 支持强制刷新
   - `updateProfile()` 内部刷新缓存
   - `clearProfile()` 清空缓存
   - 增加并发去重（`loadPromise` 复用）
   - 明确自动重试策略（次数/间隔/触发点/取消机制）
   - 明确错误处理策略（逻辑层不回退，交互层允许保留旧头像）

### Phase 2: Chat 页面
2. 修改 `frontend/wx-minipg/pages/chat/chat.ts`
   - `onLoad` 不再读取 `userInfo.avatar`
   - `onLoad` 优先使用 `profileService.getProfile()` 读取缓存；无缓存时再 `loadProfile()`
   - `onShow` 仅在缓存过期或需要强刷时调用 `loadProfile()`
   - `getUserInfo()` 仅用于 `qiao_id` 校验

### Phase 3: Profile 页面
3. 修改 `frontend/wx-minipg/pages/profile/profile.ts`
   - 页面资料显示仅从 `profileService` 读取
   - `onShow` 触发 `profileService.loadProfile()` 并渲染头像/昵称

### Phase 4: 头像更新流程
4. 修改 `frontend/wx-minipg/pages/profile-detail/profile-detail.ts`
   - 更新头像成功后：`await profileService.loadProfile(true)`
   - 然后再刷新页面显示

### Phase 5: 登录/登出流程
5. 修改 `frontend/wx-minipg/utils/auth-service.ts`
   - 登录成功后触发 `profileService.loadProfile()`（不阻塞登录）
   - 退出登录时调用 `profileService.clearProfile()`（在清理 token/userInfo 前）
   - `mapProfileToStoredUser()` 仅保留 `qiao_id`

### Phase 6: 删除过时字段
6. 修改 `frontend/wx-minipg/utils/storage.ts`
   - `StoredAuthUser` 仅保留 `qiao_id`
   - 删除 `nickname`/`avatar` 字段
7. 全量搜索并移除 `StoredAuthUser.avatar/nickname` 的读写代码
8. 确保 `getUserInfo()` 在所有场景下都能返回有效 `qiao_id`

### Phase 7: 全局头像读取点统一
9. 全量搜索 “当前用户头像/昵称” 读取点（会话列表、消息气泡、本地渲染），统一改为 `profileService`

---

## 五、影响范围
- `frontend/wx-minipg/pages/chat/chat.ts`
- `frontend/wx-minipg/pages/profile/profile.ts`
- `frontend/wx-minipg/pages/profile-detail/profile-detail.ts`
- `frontend/wx-minipg/utils/profile-service.ts`
- `frontend/wx-minipg/utils/auth-service.ts`
- `frontend/wx-minipg/pages/login/login.ts`
- `frontend/wx-minipg/pages/setup/setup.ts`
- `frontend/wx-minipg/utils/storage.ts`
- 可能涉及：`frontend/wx-minipg/utils/message/*`（仅使用 `qiao_id`，不涉及头像）
- 可能涉及：会话列表/消息气泡/本地渲染相关页面或组件

---

## 六、验收标准
- 更新头像后：profile、chat、会话列表、消息气泡等所有页面显示一致的新头像，无需重启。
- 代码中不存在 `StoredAuthUser.avatar/nickname` 字段。
- UI 不再从 storage 读取头像，不存在 fallback。
- 登录失败不会因 profile 加载失败而阻塞，但头像显示必须依赖 `profileService` 的加载结果。
- 头像加载失败时保留旧头像并自动重试，成功后自动更新。

---

## 七、测试场景
1) 头像更新同步：
- 进入 chat 页面 → 记录头像 → 更新头像 → 返回 chat
- 期望：chat 显示新头像

2) 多页面一致性：
- 打开 profile/chat/会话列表/消息气泡 → 更新头像 → 逐一检查
- 期望：所有页面一致

3) 缓存过期刷新：
- 等待 > TTL → 返回 chat/profile
- 期望：自动触发 loadProfile 重新拉取

4) 失败重试：
- 模拟 profile 拉取失败（断网/接口失败） → 进入 chat/profile
- 期望：旧头像保留 + 静默重试，恢复网络后自动显示新头像

5) 多账号切换：
- 登录账号 A → 更新头像 → 登出 → 登录账号 B
- 期望：账号 B 不显示账号 A 的头像

6) 并发请求：
- 同时打开多个页面（chat + profile）
- 期望：只发起一次 loadProfile 请求

7) 缓存边界：
- 在 TTL 临界点进入页面
- 期望：正确判断是否需要刷新

---

## 审批
批准后进入实施阶段。
