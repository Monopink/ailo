# 系统配置接口

## 接口列表

- [获取人机验证配置](#获取人机验证配置) - `GET /api/v1/system/captcha-config`

---

## 获取人机验证配置

### 基本信息

- **路径**: `GET /api/v1/system/captcha-config`
- **认证**: Bearer Token（必需）
- **说明**: 预留接口，供未来统一下发 CAPTCHA/Turnstile 等配置

### 业务说明

- 当前版本尚未开放任何字段，返回体为空对象
- 小程序/前端暂时写死 CAPTCHA/Turnstile 等站点配置常量，待接口输出字段后再从后端拉取配置
