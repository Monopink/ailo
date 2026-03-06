# 系统配置接口

## 接口列表

- [获取人机验证配置](#获取人机验证配置) - `GET /api/v1/system/captcha-config`

---

## 获取人机验证配置

### 基本信息

- **路径**: `GET /api/v1/system/captcha-config`
- **认证**: Bearer Token（必需）
- **Headers**:
  - `X-Client` (可选): 标识调用端，例如 `mini-program`。后端将按照 `client` 前缀匹配配置键（`{client}_captcha_provider` 等），未提供或查不到时回落到全局配置。
- **说明**: 统一下发目前启用的验证码提供方与相关参数，前端在初始化 Turnstile/阿里云验证码组件前必须先调用本接口。

### 成功响应 (200)

```json
{
  "provider": "none",
  "scene_id": "",
  "region": "",
  "mode": "disabled",
  "language": "cn"
}
```

**字段说明**:

- `provider` (string) - 验证码服务提供方标识，统一转为小写，目前支持 `turnstile`/`none`
- `scene_id` (string) - 验证场景 ID（不同客户端可配置不同值），后端会根据 `X-Client` 头查找 `{client}_captcha_scene_id`
- `region` (string) - 运行地域，目前固定 `cn`
- `mode` (string) - 交互模式，默认为 `popup`
- `language` (string) - 语言标识，默认为 `cn`

### 错误响应

**401 Unauthorized**:

- `"认证失效，请重新登录"` - Token 无效或已过期

**500 Internal Server Error**:

- `"系统错误（error_code）"` - 服务器内部错误

### 业务说明

- 所有值来自 `system_configs`，优先读取客户端前缀配置，找不到再回退到全局配置（`captcha_provider`、`captcha_scene_id` 等）。
- 当前微信小程序配置为 `provider=none`，如需为其它客户端启用验证码，只需在配置表中为对应 `X-Client` 设置 `turnstile` 即可，无需发版。
- 前端应在应用启动或登录前调用一次，并将结果缓存到内存，后续验证码组件直接读取；若配置可能动态调整，可在应用恢复前台时重新拉取。
