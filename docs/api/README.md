# API 接口文档

## 通用规范

- 成功响应 (HTTP 200): 直接返回业务数据，无包装
- 错误响应 (HTTP 4xx/5xx): 用户侧接口与 WebSocket 使用错误码规范，管理端接口使用 detail/request_id 规范（登录前请求按隐藏错误规则），详见 [错误码规范](error-codes.md)
- 时间格式规范见 [时间格式规范](docs\spec\time-format.md)，所有接口涉及时间字段均遵循此规范。
- API路径中尽量不包含第三方服务名称（如LeanCloud、Aliyun等）
- API 文档不硬编码枚举值，统一引用 `backend/app/enums/common.py`

### Nginx 配置同步

- 新增或调整 API 路径时，必须同步检查网关转发规则是否覆盖该路径。
- 当前 staging/prod 默认共用网关模板：`nginx/conf.d/app.conf`（由 `nginx/entrypoint.sh` 渲染到容器内 `default.conf`）。
- `nginx/conf.d/prod.conf`、`nginx/conf.d/staging.conf` 为历史配置，不是默认生效入口；除非显式设置 `NGINX_TEMPLATE`，否则不会被加载。

### 速率限制

**短信验证码**:

- 速率限制：1次/60秒（同一号码）
- 白名单：支持配置白名单号码（不受限制）

**用户认证**:

- 速率限制：10次/小时
- 失败次数限制：5次失败后锁定
- 锁定时长：15分钟

**消息发送**:

- 短期限制：5条/10秒
- 长期限制：20条/分钟

**通用API**:

- 通用限制：100次请求/分钟/IP
- 白名单：支持配置白名单IP（不受限制）
