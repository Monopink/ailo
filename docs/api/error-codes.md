# API 错误码规范

## 目标

- 所有面向用户的接口错误返回统一为 error_code、message、request_id
- 管理员接口可以不遵守此约定，直接返回明确错误内容
- 错误码可稳定用于前端分支、日志检索与告警聚合
- 用户错误返回友好文案，平台异常不暴露内部细节
- 安全风控命中对外保持同态混淆，避免暴露风控规则

## 对齐范围

- GET/POST/... /api/v1/*
- GET /ws/messages（握手与业务帧错误）
- /admin-api/* 使用本文“管理端接口错误响应规范”

## 管理端接口错误响应规范（/admin-api/*）

### 响应体格式

~~~json
{
  "detail": "duplicate key value violates unique constraint \"uq_ai_dimension_name\"",
  "request_id": "req_20260226_abcd1234",
  "error_type": "validation_error",
  "debug": {
    "exception": "UniqueViolationError",
    "sqlstate": "23505",
    "traceback": "Traceback (most recent call last): ..."
  }
}
~~~

字段说明：

- detail：管理端可直接展示的详细错误原因（必填）
- request_id：请求追踪 ID（响应体与 X-Request-ID 响应头一致，必填）
- error_type：错误分类（可选，推荐固定枚举）
- debug：结构化调试信息（可选）

### 状态码语义

| HTTP 状态码 | 语义 |
|-------------|------|
| 400 | 参数错误、业务校验失败 |
| 401 | 管理员未登录或会话失效 |
| 403 | 管理员无权限执行当前操作 |
| 404 | 管理对象不存在 |
| 409 | 资源状态冲突或重复资源 |
| 422 | 请求结构不合法 |
| 5xx | 平台异常 |

### 文案规则

- 4xx 与 5xx 的 `detail` 都必须返回具体原因
- 管理端允许返回堆栈、SQL 错误、第三方错误码与原始错误信息
- 管理端前端错误分支统一依赖 `detail` 字段，`debug` 用于排障展示

### 登录前错误隐藏规则

- 适用范围：管理端登录接口、未登录状态下访问 `/admin-api/*` 的请求
- 上述范围的响应仅返回通用 `detail` 与 `request_id`，不返回 `debug`
- 登录接口风控命中、凭证校验失败、频控命中使用同态通用文案，不区分具体失败原因
- 具体失败原因仅记录在服务端日志，通过 `request_id` 关联排查

## 用户侧统一错误响应格式

~~~json
{
  "error_code": 11010001,
  "message": "验证码错误，请重新输入",
  "reason": "VERIFICATION_CODE_INVALID",
  "request_id": "req_20260218_abc123"
}
~~~

字段说明：

- error_code：8 位数字（SSMMEEEE）
- message：用户可读文案
- reason：可选的机器可读原因码（仅在需要前端细分处理的业务错误返回）
- request_id：请求追踪 ID（响应体与 X-Request-ID 响应头一致）

WebSocket `error` 帧（`type=error`）使用同一字段：

~~~json
{
  "type": "error",
  "ws_frame_id": "frame_id",
  "payload": {
    "error_code": 24031001,
    "message": "请求参数错误",
    "reason": "REQUEST_VALIDATION_ERROR",
    "request_id": "req_20260218_abc123"
  }
}
~~~

## 用户侧文案规则

### 一、可纠正错误（普通用户错误）

- 返回友好、简洁、可执行提示
- 前端分支只依赖 error_code，禁止依赖 message

### 二、保护性拒绝（安全风控错误）

- 不使用专用固定错误码
- 必须与同模块某个常见可纠正错误完全同态：同 HTTP 状态码、同 error_code、同 message
- 禁止根据风控命中原因返回差异化文案、错误码或状态码
- 风控真实原因仅允许记录在日志（risk_reason / risk_rule_id / request_id / internal_risk_code），禁止对外返回
- 对外 `reason` 可返回稳定枚举（例如 `ATTACK_DETECTED`、`IP_BLOCKED`）用于客户端流程控制，但不得据此泄露规则细节

### 三、平台异常（系统错误）

- 仅 5xx 场景强制文案：系统错误（error_code）
- 禁止返回内部细节（配置缺失、第三方服务异常、SQL/堆栈信息等）

## 用户侧编码结构（SSMMEEEE）

- SS：服务注册码（2 位）
- MM：模块注册码（2 位）
- EEEE：模块内业务错误注册码（4 位）

说明：error_code 与 HTTP 状态码解耦。HTTP 状态码由错误条目显式声明，不允许从 error_code 反推。

---

## 注册表 A：服务注册码（SS）

| SS | 服务名 | 说明 | 状态 |
|----|--------|------|------|
| 11 | Auth | 认证与登录 | active |
| 12 | AccountSecurity | 账号安全（邮箱/手机号） | active |
| 13 | Users | 用户资料与账户信息 | active |
| 21 | Contact | 联系人与联系人申请 | active |
| 22 | Discovery | 发现页 | active |
| 23 | Media | 媒体上传与资源 | active |
| 24 | Message | 消息通道与事件接入 | active |
| 26 | System | 系统配置接口 | active |
| 80 | AdminApi | 管理端 API | optional |
| 90 | Platform | 平台通用兜底 | active |

## 注册表 B：模块注册码（MM）

| SS | MM | 模块名 | 路径前缀 | 状态 |
|----|----|--------|----------|------|
| 11 | 01 | auth | /api/v1/auth | active |
| 12 | 01 | account_security | /api/v1/user/email、/api/v1/user/phone、/api/v1/user/verify | active |
| 13 | 01 | users | /api/v1/user/profile、/api/v1/user/account、/api/v1/user/username/check、/api/v1/user/minor-mode | active |
| 21 | 01 | contacts | /api/v1/contacts | active |
| 21 | 02 | contact_requests | /api/v1/contact-requests | active |
| 22 | 01 | discovery | /api/v1/discovery | active |
| 23 | 01 | media | /api/v1/media | active |
| 24 | 01 | messages | /api/v1/messages | active |
| 24 | 03 | ws_messages | /ws/messages | active |
| 26 | 01 | system | /api/v1/system | active |
| 26 | 02 | pages | /api/v1/pages | active |
| 80 | 01 | admin_api | /admin-api | optional |
| 90 | 01 | platform | fallback | active |

## 注册表 C：业务错误码（EEEE）

### 维护规则（强制）

1. EEEE 在模块内唯一，已发布后不可复用
2. 每个错误条目必须显式登记：http_status、message_template、error_category
3. 禁止通过 HTTP 状态码自动推导 EEEE
4. 保护性拒绝必须引用同模块常见可纠正错误码，不得使用专用风控码

### 推荐号段（模块内）

| EEEE 范围 | 语义 | 说明 |
|-----------|------|------|
| 0001-1999 | 可纠正用户错误 | 参数、校验、业务前置条件、状态冲突 |
| 2000-3999 | 权限与访问控制 | 未认证、无权限、资源不可见 |
| 4000-6999 | 资源与流程状态 | 资源不存在、流程冲突、重复操作 |
| 7000-8999 | 频控与配额 | 速率限制、额度限制 |
| 9000-9999 | 模块内平台异常 | 5xx，文案统一 系统错误（error_code） |

---

## 保护性拒绝落地规则

当错误分类为保护性拒绝时：

1. 选择同模块一个常见可纠正错误作为混淆目标（例如验证码错误）
2. 对外响应完全复用该目标错误三元组：HTTP + error_code + message
3. 风控原因只写内部日志字段，不进入响应体

---

## 维护流程

1. 新增业务路径前缀时，先登记 SS/MM
2. 新增错误分支时，先在模块注册表登记 EEEE（含 http_status、文案、分类）
3. 前端分支只依赖 error_code，禁止依赖 message
4. 仅 5xx 文案带码：系统错误（error_code）
5. 契约测试必须覆盖：
   - 响应结构完整性（error_code / message / request_id）
   - 保护性拒绝同态约束
   - 5xx 文案规则
6. CI 必须执行注册表-后端实现-前端映射-文档样例一致性检查
