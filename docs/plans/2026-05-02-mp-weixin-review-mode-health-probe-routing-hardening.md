# 小程序审核分流稳态与网关拦截并行实施方案

生效日期：2026-05-02

## 问题与发现

- `2026-05-01` 至 `2026-05-02` 的 prod 运行态样本存在 `ua_fetch_status=3` 且 `segment_type=0` 的未登录启动记录，说明部分审核设备无法稳定获取运行态 UA，启动分流会回落到普通登录路径。
- `2026-05-01 16:16:11 UTC` 出现审核特征 UA 对 `POST /api/v1/auth/wechat/login` 的 `503`，同分钟出现 `auth/logout` 的 `503`，与网关 `auth` 路由限流触发模式一致。
- `2026-05-01` 审核特征 UA 对 `GET /api/v1/pages/user_agreement` 与 `GET /api/v1/pages/privacy_policy` 存在 `200` 响应，协议页面服务端内容可用。
- 微信官方安全测试通知说明测试请求会带 `Tencent Security Team` 标识，并可能来自官方公开测试 IP。

## 目标

- 审核路径与普通路径解耦：审核期未登录用户在可达场景优先进入 `square-demo`，不可达场景按 36 小时离线窗口进入 `preview-index`。
- 启动探测非阻塞：`boot` 页面在探测失败或超时时快速完成路由，不出现长时间停留。
- 网关层对已确认自动化安全探测 UA 进行直接拦截，避免污染登录链路观测样本。

## 非目标

- 不改已登录用户主业务页面结构。
- 不改审核账号 `review_scope` 数据模型与升级规则。

## 强制决策

### 1. 审核模式开关

- 系统配置新增 `mp_weixin_review_mode`（boolean）。
- 无 token 的 `preflight-probe` 请求：
  - `mp_weixin_review_mode=true` 返回 `segment_type=1`
  - `mp_weixin_review_mode=false` 按现有运行态判定链路返回

### 2. 启动路由（无 token）

- 启动先走轻量 `GET /api/v1/client/health`，短超时，失败立即兜底，不阻塞 `boot`。
- 路由矩阵：
  - 健康探测失败 + 构建后 36 小时内 -> `preview-index`
  - 健康探测失败 + 构建后超过 36 小时 -> `login`
  - 健康探测成功 + `segment_type=1` -> `square-demo`
  - 健康探测成功 + `segment_type=0` -> `login`

### 3. 网关 UA 拦截

- 拦截执行以 UA 判定为主（`OR`）：
  - 精确命中完整样本 UA
  - 命中 `tencent security team`
  - 命中组合特征 `windowswechat/wmpf + miniprogramenv/windows + xweb/1000`
- 命中后直接 `403`，不进入后端业务链路。
- 官方公开测试 IP（`106.55.202.118`、`113.96.223.69`、`125.39.132.125`）仅用于日志标记，不作为拦截前提。

## 实施内容

### A. 后端

- 在 `system_configs` 增加 `mp_weixin_review_mode` 初始配置。
- 调整 `POST /api/v1/client/preflight-probe`：
  - 保留鉴权用户 `review_scope=1` 直接返回 `segment_type=1`
  - 无 token 且 `mp_weixin_review_mode=true` 时直接返回 `segment_type=1`
  - 其他场景保持运行态特征判定
- 为审核模式覆盖路径增加结构化日志字段。

### B. 小程序前端

- `boot` 页面新增健康探测调用，探测失败/超时不阻塞启动路由。
- 无 token 启动路由改为“健康探测 -> preflight-probe -> route”链路。
- 保留 36 小时离线窗口，仅在健康探测失败分支生效。

### C. Nginx 网关

- 在 `nginx/conf.d/app.conf` 新增 UA 拦截映射：
  - `ua_block_exact`
  - `ua_block_pattern`
  - `ua_block_final`
- 在 `/api/v1/auth/` 与 `/api/v1/` 入口加统一拒绝分支（`403`）。
- access log 增加拦截命中标识与官方测试 IP 标识。

### D. 文档

- `docs/api/auth.md` 补充 auth 接口网关 `403` 拒绝行为。
- `docs/api/client-review-runtime.md` 补充 runtime 接口网关 `403` 拒绝行为。

## 验收标准

- `mp_weixin_review_mode=true`、无 token、健康探测成功时，启动路径进入 `square-demo`。
- 无 token、健康探测失败且构建后 36 小时内，启动路径进入 `preview-index`。
- `boot` 页面在探测失败/超时时不长时间停留。
- 目标 UA 访问 `/api/v1/auth/wechat/login` 返回 `403`，后端无对应业务处理日志。
- 普通小程序 UA 访问关键接口状态码与耗时无异常突增。

## 实施状态

- 状态：实施中
- 最后更新：2026-05-02
