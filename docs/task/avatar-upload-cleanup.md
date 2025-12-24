# Avatar Upload Cleanup & Setup Flow Adjustment

**Date**: 2025-12-21
**Owner**: Backend/Frontend joint task
**Status**: In Progress

## 1. 背景
- 预签名/直传方案已彻底弃用，所有端统一走 `POST /api/v1/media/upload` 代理上传。
- 系统默认头像由后端提供（COS avatar/default.webp，依赖 COS CDN/Endpoint 动态拼接），所有客户端均显示接口返回的 URL。
- 旧流程要求用户在 Setup 页面完成注册，导致头像上传前无法获得 Token，引发 401。
- 目标：登录环节即完成注册，携带 Token 再跳转 Setup 进行资料补全，Setup 仅调用 `PUT /api/v1/users/profile`。

## 2. 范围
1. **后端**
   - `verify_phone` / `wechat/login`：若为新用户，直接创建账号+Profile stub，响应中新增 `needs_profile_setup`。
   - `/auth/complete-registration`：下线或转换为向后兼容提示，所有资料更新统一走 `/api/v1/users/profile`。
   - 默认头像兜底逻辑固定为 COS avatar/default.webp，由 `TENCENT_COS_CDN_DOMAIN` 或 `TENCENT_COS_ENDPOINT` 拼接得到。
2. **前端（WeChat 小程序）**
   - 登录流程保存 `needs_profile_setup`，全局路由守卫控制跳转；仅在 flag 为 true 时进入 Setup。
   - Setup 页面：使用登录 token 直接调用 `completeAvatarUpload()` + `updateUserProfile`，仅提交资料字段，不包含短信验证码或 `verified_phone_token`。
   - Profile 页面沿用同一工具函数，避免重复实现。
   - `getAvatarUrl` 去除 `fallbackToDefault`，任何兜底均来自后端返回的 URL。
3. **文档**：`docs/task/avatar-upload-implementation.md`、`docs/spec/avatar-upload-frontend.md`、`docs/api/auth.md` 更新流程描述，确保前端参照一致。

## 3. 前端实施清单
| 模块 | 任务 | 备注 |
| --- | --- | --- |
| `utils/avatar.ts` | 删除 fallback 逻辑，仅解析 URL/file_id | 默认头像由接口返回 |
| `utils/avatar-uploader.ts` | 复用，无需改架构；需确认错误提示覆盖 401/413 | |
| `utils/profile.ts` | 暴露 `updateUserProfile`（PUT `/users/profile`） | 供 Setup/Profile 共用 |
| `utils/auth-service.ts` | 存储 `needs_profile_setup`，提供 getter | |
| `app.ts` / 首页 | 登录或恢复会话后检查 flag；true → `wx.redirectTo('/pages/setup/setup')` | 防止已完成用户重复进入 |
| `pages/setup/setup` | - 删除 `verified_phone_token` 依赖<br>- 使用登录用户数据初始化<br>- 提交调用 `updateUserProfile`<br>- 成功后刷新用户缓存 & 清除 flag | 页面仍保留头像上传入口 |
| `pages/profile-detail` | 继续调用相同 `completeAvatarUpload` + `updateUserProfile`，确保逻辑一致 | |

## 4. 后端实施清单
1. `auth.verify_phone` / `auth.wechat_login`：统一返回 `{"token": "...", "user": {...}, "needs_profile_setup": bool}`。
2. `auth.complete_registration`：标记为废弃，若仍被调用则返回 409 + 明确信息。
3. `users.profile`：确保允许空 avatar（后端自动兜底）。
4. 日志：记录 `needs_profile_setup` 状态变更，便于排查首次登录流程。

## 5. 测试矩阵
| 场景 | 步骤 | 期望 |
| --- | --- | --- |
| 新用户登录 | 手机验证 → 收到 token → 立即调用 `/media/upload` | 代理上传成功返回 `{file_id,url}` |
| Setup 跳转 | 登录后 `needs_profile_setup=true` | 自动跳转 Setup，完成资料后 flag 置 false |
| 旧链接访问 `/auth/complete-registration` | 直接调用 | 返回 409/410 + 提示，日志记录 |
| 默认头像 | 不上传头像直接提交 profile | 接口返回后端默认 URL，前端展示成功 |
| 前端兜底 | 清理本地默认资源后展示 | 不出现 404/缺图 |

## 6. 依赖
- 需要数据库可写权限用于自动创建 Profile stub。
- MinIO/COS 账号保持可用以验证 `/media/upload` 上传。
- WeChat devtools 需更新合法域名，指向新的 backend 域名。
- `deployment/.env` 中 `CORS_ORIGINS`/`ADMIN_CORS_ORIGINS` 应包含本地 devtools 域名，`DB_*` 需与实际 Postgres 实例一致（默认容器：host `postgres`，user `ailo_user`）。

## 7. 交付物
- 更新后的 API/规范文档。
- 相关前端/后端 MR（含测试报告）。
- 本任务文档完成签字后移入 `docs/task/` 归档。随后若任务完成，可在 `current_tasks.md` 中删除对应条目。
