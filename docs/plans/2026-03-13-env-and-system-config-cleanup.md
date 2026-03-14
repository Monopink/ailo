# 环境变量与 system_configs 优化方案

## 目标
- 敏感密钥与 LeanCloud app_id 迁移到环境变量
- 移除 system_configs 悬空项与用户侧 CAPTCHA 逻辑
- 仅保留实际生效的配置项，不做兜底回退

## 约束
- 敏感密钥与 LeanCloud app_id 仅通过环境变量提供
- 其他业务配置以 system_configs 为准
- 读取逻辑不设置默认兜底
- 用户侧不启用 CAPTCHA

## 变更清单
### 环境变量
- 新增环境变量：`LEANCLOUD_IM_APP_ID`
- 新增环境变量：`LEANCLOUD_IM_APP_KEY`
- 新增环境变量：`ADMIN_TURNSTILE_SECRET_KEY`
- 新增环境变量：`ADMIN_TURNSTILE_SITE_KEY`
- 保持已有环境变量：`LEANCLOUD_MASTER_KEY`

### system_configs（删除）
- `leancloud_im_app_id`
- `leancloud_im_app_key`
- `admin_turnstile_secret_key`
- `admin_turnstile_site_key`
- `captcha_threshold_failures`
- `ws_ping_interval_seconds`
- `jwt_algorithm`
- `jwt_sliding_window_days`
- `token_max_active_per_device`
- `token_cleanup_after_days`
- `api_whitelist`
- `image_max_size_mb`
- `image_allowed_formats`
- `image_upload_daily_quota`
- `image_upload_daily_size_quota_mb`

### system_configs（新增）
- `refresh_token_expires_in_days`

### system_configs（继续保留并接线）
- `max_message_length_chars`
- `sms_code_expires_in_seconds`
- `sms_code_length_digits`

### 逻辑调整
- LeanCloud 配置读取：app_id/app_key 由环境变量读取，server_url 由 system_configs 读取
- Turnstile site key / secret key：仅从环境变量读取
- refresh_token_expires_in_days：读取失败直接报错
- 用户侧 CAPTCHA：移除配置与调用路径

## 影响范围
- `backend/app/services/config.py`
- `backend/app/services/security/captcha/factory.py`
- `backend/app/api/v1/auth.py`
- `backend/app/api/v1/system.py`
- `backend/app/services/security/auth_tracker.py`
- `backend/app/schemas/ai/chat.py`
- `backend/database/init/sql/02_required_data*.sql`
- `deployment/*/.env.example`

## 风险与处理
- 未配置 `refresh_token_expires_in_days` 将导致刷新流程报错
- 未配置 `ADMIN_TURNSTILE_SECRET_KEY` 或 `ADMIN_TURNSTILE_SITE_KEY` 且启用 admin CAPTCHA 时将导致后台登录验证不可用
- LeanCloud app_id/app_key 未配置将导致 IM 相关流程报错

## 验证
- 启动后读取配置无默认兜底
- 后台登录在开启 CAPTCHA 时可正确验证
- 发送短信验证码使用配置化 TTL/长度
- 用户侧无 CAPTCHA 依赖

## Deployment .env 模板
- 基线模板：`deployment/.env.example` -> 运行时基线文件：`deployment/.env`
- 环境覆盖模板：`deployment/dev/.env.example`、`deployment/staging/.env.example`、`deployment/prod/.env.example`
- Docker compose 同时加载基线与覆盖：`deployment/*/compose.yaml` 的 `env_file`
