# 双 Token 认证改造任务

## 1. 背景与缘由
- 当前前端在 `App.onShow` 中调用 `/auth/refresh-token` 以续期，但后端并不存在该接口，日志持续 404（`[App] Refresh token failed {"error":"Not Found"}`）。
- 认证系统只签发单一 JWT，过期后用户必须重新登录；长会话（聊天、上传）过程中一旦 access token 失效会直接中断体验。
- `user_tokens` 表已经存储 token、到期时间和设备信息，具备演进为 refresh 体系的基础；实现标准的 access+refresh 流程可消除伪调用并满足持续会话需求。

## 2. 目标
1. 提供正式的 `POST /api/v1/auth/refresh-token`，使用 refresh token 换取新的 access token。
2. 登录/注册成功后返回 `{ access_token, refresh_token }`，并在 `user_tokens` 中持久化 refresh 字段与 `token_metadata`。
3. 前端 `authService` 在 access token 将过期或 API 返回 401 时自动刷新，刷新失败才引导重新登录。
4. 移除当前无效的刷新调用，确保日志干净、鉴权行为一致。

## 3. 现状梳理
- 表结构：`user_tokens` 字段包括 `access_token/access_expires_at/status/last_activity_at`（`backend/database/init/01_schema.sql:69-85`）。
- Token 生成：`_issue_jwt_token_for_user()` 调用 `generate_jwt_token` 并写入一条 `user_tokens` 记录（`backend/app/api/v1/auth.py:214`）。
- 校验：`get_current_user()` 通过查 `user_tokens` + 过期时间判断，未做续期（`backend/app/api/deps.py:108`）。
- 前端：`authService.refreshToken()` 直接 `post('/auth/refresh-token')`，所以一直 404。

## 4. 实施方案
### 4.1 数据库
**字段变更**：

```sql
ALTER TABLE user_tokens
ADD COLUMN refresh_token_hash VARCHAR(512),
ADD COLUMN refresh_expires_at TIMESTAMP WITH TIME ZONE,
ADD COLUMN refresh_revoked_at TIMESTAMP WITH TIME ZONE,
ADD COLUMN token_metadata JSONB DEFAULT '{}'::jsonb;
```

`token_metadata` 专门用于扩展信息（续期计数、异常标记、设备指纹等）。

**索引变更**：

```sql
CREATE UNIQUE INDEX idx_user_tokens_refresh_hash
ON user_tokens(refresh_token_hash)
WHERE refresh_token_hash IS NOT NULL;
```

历史数据的 refresh 字段保持 NULL。用户下次登录时自动补齐 refresh token，无需强制整体下线。

### 4.2 后端 API
**Token 生成规范**：

```python
import secrets
import hashlib

refresh_token = secrets.token_urlsafe(64)  # 512 bits
refresh_token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
refresh_expires_at = datetime.now(UTC) + timedelta(days=settings.refresh_token_expires_in_days)
```

**登录/验证入口**
- `VerifyPhoneResponse` 返回 `{ access_token, refresh_token, expires_in }`。
- `_issue_jwt_token_for_user()` 同时写入 `refresh_token_hash / refresh_expires_at / token_metadata`。

**刷新接口** `POST /api/v1/auth/refresh-token`

- 请求体 `{ refresh_token }`；接口显式 `auth: false`。
- 流程：
  1. 计算 hash，定位 `status=1` 且 `refresh_revoked_at IS NULL` 的记录。
  2. 校验 `refresh_expires_at > now()`。
  3. 限流：单个 refresh token 每分钟最多刷新 5 次（MVP：内存缓存；正式：Redis）。
  4. 生成新的 access token（更新 `access_token`、`access_expires_at`、`last_activity_at`）。Refresh token 默认 **不轮换**，减少客户端复杂度。
- 并发刷新：允许同一 refresh token 并发调用，所有 access token 有效；客户端通过 Promise 去重减少重复请求。

**吊销逻辑**
- 登出、后台风控、挤下线等场景设置 `status=2` 或 `refresh_revoked_at = now()`，立即阻断刷新。

**配置项**
- `access_token_expires_in_days`（默认 7）。
- `refresh_token_expires_in_days`（默认 90）。命名统一使用 `refresh_token_expires_in_days`。

### 4.3 前端
- `STORAGE_KEYS` 新增 `REFRESH_TOKEN`。
- `authService.login()`：保存 `{ accessToken, refreshToken }`，并更新 `_token`。
- `authService.refreshToken()`：
  - 使用 `_refreshPromise` 去重；
  - 读取 `STORAGE_KEYS.REFRESH_TOKEN`，无值直接抛错；
  - 调用 `post('/auth/refresh-token', { refresh_token }, { auth: false })`；
  - 返回新的 access token（如后端返回新的 refresh token 也可同时覆盖）。
- `authService.logout()`：移除 `AUTH_TOKEN / REFRESH_TOKEN / USER_INFO / PROFILE_SETUP_REQUIRED`，再调用 `/auth/logout`。
- `utils/api`：
  - `request()` 在收到 401 且未重试时，调用 `authService.refreshToken()`，成功后重放一次原请求；刷新失败则跳转登录。
- `App.refreshTokenIfNeeded()` 可删除，刷新统一由 API 层触发。

### 4.4 迁移与回滚
- DB Migration：添加字段 + 索引，历史数据 refresh 字段设 NULL；待客户端升级完毕后可要求重新登录生成 refresh token。
- 部署顺序：
  1. 上线后端（接口+表结构），保持兼容旧客户端（支持只带 access token 的登录响应）。
  2. 发版前端新版本（使用 refresh token），待渗透后再逐步要求强制更新。
- 回滚：若 refresh 出现问题，可让 `refresh_expires_at` 立即过期，同时在前端切回“401 即重新登录”。

## 5. 依赖与风险

- **依赖**：数据库迁移工具、系统配置（新增 `refresh_token_expires_in_days`）、限流组件（内存或 Redis）。
- **风险**：
  - 暴力枚举 refresh token → 通过哈希存储 + 限流/日志追踪降低风险。
  - 并发刷新 → 前端 Promise 去重 + 后端允许并发。
  - 老版本客户端 → 响应继续保留旧 `token` 字段，避免一次性强制升级。

## 6. 验收标准

**后端测试**
- `_issue_jwt_token_for_user` 返回双 token，hash 写入正确。
- `/auth/refresh-token` 覆盖成功、过期、吊销、限流等场景。
- 登出/风控后 refresh token 无法再刷新。

**前端测试**
- `authService.login`、`refreshToken`、`logout` 流程单测。
- `utils/api` 对 401 的自动刷新逻辑在 setup/profile 页面验证通过。
- 并发触发多次刷新时只发一次请求。

**集成场景**
1. 登录 → 长时间停留 → API 触发刷新 → 请求成功。
2. 人工设置 refresh token 过期 → 刷新失败 → 跳转登录。
3. 多设备登录，后台吊销某个 refresh token → 该端无法刷新，其他端不影响。
4. 网络抖动导致刷新失败 → 正确提示/跳登。

**性能/安全**
- `/auth/refresh-token` 响应 <200ms，限流命中返 429。
- Refresh token 明文不出现在日志，仅存 hash。
- 旧客户端（无 refresh token）仍能登录，只是无法刷新。

## 7. 实施注意事项

**开发顺序**
1. 数据库迁移：编写/执行字段与索引脚本，验证 schema。
2. 后端实现：登录/刷新/登出、限流、日志与测试。
3. 前端实现：`STORAGE_KEYS`、`authService`、`utils/api`、登录/登出页面。
4. 集成测试：覆盖正常与异常流程。

**部署检查清单**
- [ ] 数据库迁移记录。
- [ ] 后端单测与 OpenAPI 更新。
- [ ] 前端 `npm run check` 通过。
- [ ] 日志中不再出现 `/auth/refresh-token 404`。

**部署后监控**
- `/auth/refresh-token` 调用量与成功率。
- 401 错误趋势。
- 用户侧反馈（是否仍频繁掉线）。

**回滚方案**
- 后端保持兼容（老客户端仅用 access token）。
- 前端若需回退，只需移除刷新逻辑，并保留 access token 流程。
- 数据库新增字段可保留不用，无需回滚。
