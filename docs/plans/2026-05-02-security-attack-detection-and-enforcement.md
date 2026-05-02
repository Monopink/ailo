# 攻击行为检测与自动惩罚全链路实施方案

生效日期：2026-05-02

## 问题与现状

- 线上已出现针对 `client_runtime_observations` 的恶意输入样本（SQL 注入探测、异常路径拼接、恶意参数构造），说明存在自动化攻击流量进入业务接口。
- 当前系统具备 `user_violation_logs`、`user_risk_stats`、`users.status` 与 `user_tokens` 基础能力，但攻击事件记录主要覆盖 AI 对话 `attack_detected` 路径，未形成统一处罚执行链路。
- 当前 Nginx 已具备基础限流与特定 UA 拦截能力，但缺少面向通用 API 攻击特征的边缘拦截与自动封禁联动。

## 目标

- 建立统一攻击检测与处罚闭环：攻击命中后落库、计分、踢登录、封号、封 IP 全链路可审计。
- 建立独立双轨处罚策略：用户处罚与 IP 处罚互不依赖、分别触发。
- 对高危攻击实现单次命中即处罚，避免攻击流量在应用层反复消耗资源。
- 在网关层前置拦截高危 URI/Query 探测流量，减少后端处理压力。

## 非目标

- 不改业务功能路径与正常用户交互文案。
- 不引入分布式 WebSocket 踢线基础设施。

## 强制决策

### 1. 违规与风险模型

- 直接扩展 `user_violation_logs`，作为统一安全事件记录表。
- `user_risk_stats` 继续作为用户维度风险聚合表，并补齐自动处罚所需统计字段。
- `ViolationType` 采用攻击聚焦枚举（移除未使用内容违规分类）：
  - `1=prompt_injection`
  - `2=sql_injection`
  - `3=command_injection`
  - `4=path_traversal`
  - `99=other`
- 历史映射策略（迁移一次性收敛）：
  - `old 6 -> new 2`
  - `old 7 -> new 3`
  - `old 8 -> new 4`
  - `old 9 -> new 99`
  - `old 2/3/4/5 -> new 99`
  - `user_risk_stats.violation_by_type` 中 `abuse_content/spam/harassment` 归并到 `other`

### 2. 处罚策略

- 用户处罚轨（独立）：
  - 条件：命中高危攻击且可定位到用户账号
  - 动作：
    - 账号状态改为 `suspended`
    - 撤销该账号所有有效 token
    - 更新用户风险统计
- IP 处罚轨（独立）：
  - 条件：同一 IP 攻击次数达到阈值
  - 动作：执行 TTL 封禁
- 高危攻击单次命中只触发用户处罚轨；IP 仅记录与累计，不执行立即封禁。
- 非高危规则命中仅记录与累计，不触发立即封号。

### 3. IP 封禁

- 封禁采用 TTL 策略，不使用永久封禁。
- 首版默认时长：
  - 高危阈值命中：24 小时
- 首版阈值：
  - 高危：5 分钟窗口内同一 IP 命中次数 `>= 8`

### 4. 高危规则范围（首版）

- SQL 注入探测
- 命令注入探测
- 恶意路径探测

### 5. WebSocket 范围

- 当前 WebSocket 以管理后台用途为主，首版采用高性价比方案：
  - 握手与消息处理链路执行用户状态与封禁检查
  - 命中后立即断开连接
- 暂不引入跨进程实时踢线广播。

## 实施内容

### A. 数据模型与迁移

- 扩展 `user_violation_logs` 字段，覆盖统一攻击事件上下文：
  - `rule_code`、`rule_version`、`detection_source`
  - `http_method`、`request_path`、`client_ip`、`request_id`
  - `evidence_payload`（JSONB）、`trigger_score`
- 扩展 `user_risk_stats` 字段，支持用户处罚轨统计：
  - `high_risk_hits`、`last_high_risk_at`
  - `last_suspend_at`
- 新增 IP 风险统计表（阈值判定模型）：
  - `security_ip_risk_stats`（IP、窗口计数、累计计数、最近命中时间、最近规则）。
- 新增 IP 封禁表（TTL 模型）：
  - `security_ip_blocks`（IP、原因、规则、封禁时间、过期时间、状态）。

### A.1 `security_ip_risk_stats` 表设计（IP 独立计数）

- 表名：`security_ip_risk_stats`
- 主键：`id BIGINT`（snowflake）
- 字段定义：
  - `ip_address INET NOT NULL`
  - `high_risk_count_5m INTEGER NOT NULL DEFAULT 0`
  - `medium_risk_count_10m INTEGER NOT NULL DEFAULT 0`
  - `total_attack_count INTEGER NOT NULL DEFAULT 0`
  - `last_attack_at TIMESTAMPTZ NULL`
  - `last_rule_code VARCHAR(64) NULL`
  - `last_source VARCHAR(32) NULL`
  - `last_request_path VARCHAR(255) NULL`
  - `last_user_id BIGINT NULL`
  - `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
  - `updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
- 约束：
  - `high_risk_count_5m >= 0`
  - `medium_risk_count_10m >= 0`
  - `total_attack_count >= 0`
- 索引：
  - `uq_security_ip_risk_stats_ip (ip_address)` 唯一索引
  - `idx_security_ip_risk_stats_last_attack (last_attack_at)`

### A.2 `security_ip_blocks` 表设计（TTL）

- 表名：`security_ip_blocks`
- 主键：`id BIGINT`（snowflake）
- 字段定义：
  - `ip_address INET NOT NULL`：被封禁 IP（IPv4/IPv6）
  - `block_scope INTEGER NOT NULL`：当前写入值为 `1=single_ip`
  - `cidr_prefix INTEGER NULL`：当前写入为 `NULL`
  - `severity_level INTEGER NOT NULL`：`1=low`、`2=medium`、`3=high`、`4=critical`
  - `reason_code VARCHAR(64) NOT NULL`：处罚原因码
  - `rule_code VARCHAR(64) NOT NULL`：命中的规则编码
  - `rule_version VARCHAR(32) NOT NULL`：规则版本
  - `source VARCHAR(32) NOT NULL`：来源（`nginx` / `backend`）
  - `request_path VARCHAR(255) NULL`
  - `request_method VARCHAR(16) NULL`
  - `evidence_payload JSONB NOT NULL DEFAULT '{}'::jsonb`
  - `hit_count INTEGER NOT NULL DEFAULT 1`
  - `first_hit_at TIMESTAMPTZ NOT NULL`
  - `blocked_at TIMESTAMPTZ NOT NULL`
  - `expires_at TIMESTAMPTZ NOT NULL`
  - `status INTEGER NOT NULL DEFAULT 1`：`1=active`、`2=released`、`3=expired`
  - `released_at TIMESTAMPTZ NULL`
  - `release_reason VARCHAR(128) NULL`
  - `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
  - `updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
- 约束：
  - `expires_at > blocked_at`
  - `status in (1,2,3)`
  - `block_scope in (1,2)`
  - `severity_level in (1,2,3,4)`
  - `single_ip` 时 `cidr_prefix IS NULL`，`cidr` 时 `cidr_prefix` 必填且在合法范围
- 索引：
  - `idx_security_ip_blocks_ip_status_expire (ip_address, status, expires_at)`
  - `idx_security_ip_blocks_expire (expires_at)`
  - `idx_security_ip_blocks_rule_time (rule_code, blocked_at)`
  - `idx_security_ip_blocks_source_time (source, blocked_at)`
- 读取判定条件（统一）：
  - `status = 1 AND expires_at > NOW()`
- 写入策略：
  - 同一 `ip_address + status=1` 命中时，更新 `hit_count`、`expires_at`、`updated_at`
  - 未命中时插入新行
- 过期策略：
  - 定时任务将 `expires_at <= NOW()` 且 `status=1` 的记录更新为 `status=3`。

### B. 后端安全执行链路

- 新增统一安全事件写入服务：
  - 写 `user_violation_logs`
  - 更新 `security_ip_risk_stats`
- 用户处罚轨执行器（独立）：
  - 按高危规则判定用户处罚
  - 用户状态置 `suspended`
  - 撤销全部 token
  - 更新 `user_risk_stats`
- IP 处罚轨执行器（独立）：
  - 按 `security_ip_risk_stats` 阈值判定是否封禁
  - 写 `security_ip_blocks`
- 统一接入点覆盖：
  - 认证接口
  - `client` 运行态观测相关接口
  - 公共邀请 intake 接口
  - 其他已识别高风险入口
- 保护性拒绝继续遵循错误码规范，对外不暴露命中规则细节。

### C. Nginx 与 Fail2ban

- 在 `nginx/conf.d/app.conf` 增加 API 攻击特征映射（URI/Query 层），命中后直接拒绝。
- 为 `/ws/messages` 增加握手速率与并发连接限制。
- 扩展 access log 字段：`attack_flag`、`rule_code`。
- 新增 API 攻击 fail2ban filter/jail（staging/prod）：
  - 监听攻击命中日志
  - 按规则执行 TTL 封禁。

### D. 配置体系

- 在 `system_configs` 增加安全策略配置：
  - 高危 IP 封禁 TTL
  - IP 阈值窗口与次数
  - 用户处罚开关
  - 规则版本号
- 在 `bootstrap` 与环境覆盖脚本同步默认值。

### E. 文档对齐

- `docs/spec/*`：补充统一攻击检测与处罚行为规范。
- `docs/api/*`：补充安全拒绝对外契约与同态返回约束。
- `docs/plans/*`：记录本次实施结果与验收状态。

## 验收标准

- 高危攻击命中且可定位用户后：
  - 账号状态改为 `suspended`
  - 撤销该账号所有有效 token
  - 产生 `user_violation_logs` 记录
  - `user_risk_stats` 同步更新
  - `security_ip_risk_stats` 仅做计数更新，不立即封禁
- 任意攻击命中后：
  - 产生 `user_violation_logs` 记录
  - `security_ip_risk_stats` 的计数与最近命中信息更新
- 同一 IP 达到阈值后：
  - 写入 `security_ip_blocks`
  - 封禁在 TTL 窗口内生效
- Nginx 攻击特征命中后：
  - 请求不进入后端业务处理
  - 日志带 `attack_flag/rule_code`
  - fail2ban 按策略写入封禁
- 正常流量下：
  - 登录、消息、邀请等核心路径无误封与明显延迟回归。

## 实施状态

- 状态：实施中
- 最后更新：2026-05-02

### 本轮已落地（2026-05-02）

- 已落地 `ViolationType` 攻击聚焦枚举与映射迁移方案：
  - `1=prompt_injection`、`2=sql_injection`、`3=command_injection`、`4=path_traversal`、`99=other`
  - 历史值映射与 `violation_by_type` 归并规则已写入迁移脚本。
- 已落地后端安全执行链路首版：
  - 新增 `attack_detection` 与 `enforcement` 服务。
  - 新增攻击命中后统一落库、用户处罚、IP 计数与 TTL 封禁执行逻辑。
- 已落地入口接入（首批）：
  - API 中间件 `APIRateLimitMiddleware`
  - `client` 预检/运行观测入口
  - `public/invitations/intake` 公共入口
  - `auth` 核心登录链路（密码登录、微信登录/绑手机、refresh-token、手机号登录）
  - WebSocket 鉴权入口 `/ws/messages`
- 已落地边缘拦截与联动：
  - Nginx 增加 `api_attack_flag` / `api_attack_rule_code` 映射与 403 拦截
  - 新增 fail2ban API 攻击 filter/jail（staging/prod）
- 已落地管理端可观测性补齐：
  - `Violation Logs` 新增规则/来源/请求/IP/证据字段展示
  - 新增 `IP Risk Stats` 与 `IP Blocks` 两个只读视图
- 已修正阈值判定一致性：
  - 攻击命中后先 flush 违规日志，再计算 IP 窗口计数，确保本次命中参与阈值判定

### 当前阻塞与待完成

- 本地未提供完整运行环境变量，无法执行 Alembic `upgrade head` 实跑验证（Settings 校验失败）。
- 仍需在具备完整环境变量的目标环境执行：
  - `alembic upgrade head`
  - 关键链路回归与攻击场景联调验收
