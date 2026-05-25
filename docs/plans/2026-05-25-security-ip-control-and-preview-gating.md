## 文档目的

定义安全风控链路的本次实施方案：修正 `ws_ticket` 误报导致的 IP 连带封禁，新增管理员 IP 封禁/解封操作能力，并收敛小程序 `preview` 入口条件。

## 目标

- 将攻击检测从“字段统一正则扫描”调整为“字段类型驱动扫描”，避免 `opaque token` 被 SQL 规则误判。
- 将 `WS_AUTH` 风险统计与阈值从 `API_AUTH` 中拆分，避免单通道误报外溢。
- 提供管理员可用的 IP 封禁管理能力：支持手工封禁（含 CIDR、永久封禁）与解封（必填原因）。
- 小程序端仅在“服务完全不可连接”且满足离线窗口条件时进入 `preview`，风控拒绝不触发 `preview`。
- 小程序端风控场景统一用户提示文案为「服务繁忙，请稍后再试」。

## 固化决策

- IP 封禁管理：
  - 支持 `single_ip` 与 `cidr` 封禁。
  - 支持永久封禁。
  - 解封操作必须填写 `release_reason`。
  - 操作入口在 `/security_ip_blocks/list` 列表页内，通过自定义按钮+弹窗交互实现，不使用 Starlette-Admin 默认 create/edit 页面。
  - 权限：`SUPER_ADMIN` 与 `ADMIN` 可执行封禁/解封，`VIEWER` 只读。
- 小程序路由：
  - `preview` 仅在“后端完全不可连接（网络/超时等）”且满足 `build_time + 36h` 条件时进入。
  - `403/429/5xx` 归类为“服务可达但请求失败”，不得进入 `preview`。
  - 风控/服务拒绝提示文案统一为「服务繁忙，请稍后再试」。
- 规则架构：
  - `ws_ticket` 归类为 `opaque_token`，不参与 SQL/命令注入文本规则扫描。
  - `WS_AUTH` 增加独立检测源与独立阈值配置，不复用 `API_AUTH` 风险计数。

## 变更范围

- 后端安全检测与处罚：
  - `backend/app/services/security/attack_detection.py`
  - `backend/app/services/security/enforcement.py`
  - `backend/app/enums/security.py`
  - `backend/app/api/ws/messages.py`
- 后端 IP 封禁管理能力：
  - `backend/app/api/admin/*`（新增安全管理 API）
  - `backend/app/services/security/*`（新增/扩展 admin 操作服务）
  - `backend/app/admin/views/*`（新增自定义入口）
  - `backend/app/admin/templates/custom_views/*`（新增页面与弹窗）
  - `backend/app/admin/static/js/*`（新增页面逻辑）
- 小程序端运行态判定与路由：
  - `frontend/mp-weixin/utils/runtime-segment.ts`
  - `frontend/mp-weixin/pages/boot/boot.ts`
  - `frontend/mp-weixin/pages/login/*`（提示文案与状态展示）
- 文档：
  - `docs/api/client-review-runtime.md`
  - `docs/spec/client/mini-program/*`
  - `docs/api/admin-*`（新增/更新安全管理 API 文档）

## 实施步骤

1. 安全检测分型改造
   - 在攻击检测层引入字段类型策略（`free_text`、`identifier`、`opaque_token`）。
   - 将 `ws_ticket` 明确标记为 `opaque_token`，仅执行格式与签名校验。
   - 保留对 `user_agent`、路径、查询等可疑自由文本字段的攻击扫描。

2. WS 鉴权链路收敛
   - `ws_auth` 流程调整为先验签 `ws_ticket`，后执行必要风险扫描。
   - 拆分 `DetectionSource.WS_AUTH`，并在 `enforcement` 中按 source 维度隔离风险统计与封禁阈值。

3. IP 封禁管理后端实现
   - 新增手工封禁 API（支持 `single_ip/cidr`、TTL 与永久封禁）。
   - 新增解封 API（`release_reason` 必填）。
   - 写入 `admin_operation_logs` 审计，记录操作者、目标、动作、原因与封禁参数。

4. 管理后台列表页内嵌操作实现
   - 在 `/security_ip_blocks/list` 注入 `Add Block` 顶部按钮。
   - 在活动封禁记录行注入 `Release` 按钮。
   - 通过弹窗收集封禁参数/解封原因并调用 `admin-api/security/*`，列表继续只读承载审计字段。

5. 小程序 `preview` 路由判定改造
   - 健康探测返回从布尔值升级为连接状态分类（可达/不可达）。
   - 仅当“不可达”时允许走 `health_unavailable` 分支进入 `preview`。
   - 风控拒绝与服务拒绝统一提示「服务繁忙，请稍后再试」并停留正常登录/引导路径。

6. 联调与验收
   - 回归 `ws_auth`、`client/health`、`runtime-observations` 与 `boot` 路由。
   - 验证管理员封禁/解封与审计日志完整性。
   - 更新 API/spec 文档与实现一致。

## 验收标准

- `ws_ticket` 不再触发 `sql_injection_pattern` 命中；同场景不再出现由此引发的 IP 连带封禁。
- `DetectionSource.WS_AUTH` 独立生效，`WS_AUTH` 与 `API_AUTH` 风险计数与阈值互不污染。
- 管理后台可通过自定义页面执行：
  - 手工封禁：支持 `single_ip/cidr`、支持永久封禁；
  - 解封：必须填写原因，提交成功后块状态变为 `released`。
- 每次封禁/解封均写入 `admin_operation_logs`，可追溯操作者与参数。
- 小程序端在 `403` 风控拒绝场景不进入 `preview`；仅在后端完全不可连接且离线窗口有效时进入 `preview`。
- 小程序风控提示文案统一为「服务繁忙，请稍后再试」。
- `docs/api/*` 与 `docs/spec/*` 对外契约与行为描述与实现一致。

## 当前状态

- 状态：后端已完成并对齐决策，待联调（2026-05-25）。
- 已完成：
  - 攻击扫描改造为字段类型策略（含 `opaque_token` 免 SQL/命令/路径规则扫描）。
  - `ws_auth` 安全顺序落地为：客户端 IP 校验 → IP 封禁检查 → `ws_ticket` 验签/设备绑定校验 → 攻击签名检测。
  - `DetectionSource.WS_AUTH` 拆分与 source 维度风险阈值隔离。
  - `security_ip_risk_stats` 重建为 `(ip_address, detection_source)` 维度（按决策直接清空并重建，不保留旧统计）。
  - 管理后台 `admin-api/security/*` 封禁/解封接口与审计日志写入。
  - 安全管理自定义页面（封禁表单 + 解封弹窗 + 列表刷新）。
  - 文档已与后端实现对齐（含 WS 安全检查顺序与 source 维度配置规则）。
- 备注（2026-05-25）：
  - 本次后端提交与文档对齐范围不包含小程序文件；小程序 `preview` 收敛项需在对应前端提交中验收。
