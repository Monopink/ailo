# Staging 环境优化方案

## 已确认决策

- 数据库不开放公网端口。
- 数据库图形化工具访问统一通过 `SSH Tunnel`。
- 管理后台 `qiao-dash` 与管理接口 `admin-api` 保持公网可访问。
- 管理后台 `qiao-dash` 与管理接口 `admin-api` 统一启用 `Basic Auth`。
- 腾讯云安全组作为入口防火墙，公网仅开放 `SSH`、`80`、`443`。
- 继续使用自建 `PostgreSQL`，达到数据库瓶颈后再评估云数据库迁移。
- PostgreSQL 主版本升级先在开发环境完成升级测试，再进入 `staging` 与生产环境。

## 目标范围

- 收敛 `staging` 暴露面与访问路径。
- 固化后台入口双层认证策略。
- 固化数据库远程运维访问路径。
- 对齐 `staging` 与生产环境的网络边界规则。

## 变更清单

### 1. 数据库访问面

- 删除 `deployment/docker-compose.staging.yml` 中 PostgreSQL 端口映射。
- 保持 PostgreSQL 仅在容器网络内可达。
- Navicat 等工具统一通过 `SSH Tunnel` 连接 PostgreSQL。

### 2. 管理后台入口保护

- 在 `nginx/conf.d/staging.conf` 为 `/qiao-dash/` 启用 `Basic Auth`。
- 在 `nginx/conf.d/staging.conf` 为 `/admin-api/` 启用 `Basic Auth`。
- 保持后端既有管理员登录鉴权链路不变。

### 3. 网络边界

- 腾讯云安全组公网入站规则保持仅 `SSH`、`80`、`443`。
- 主机侧不新增数据库公网端口放行规则。

### 4. 配置收敛

- `deployment/.env.staging` 的 `ALLOWED_HOSTS` 收敛为明确主机名单，不包含通配 `*`。

### 5. 主版本升级路径

- 在开发环境执行 PostgreSQL 主版本升级测试。
- 升级测试通过后，同步更新 `staging` 到 `PostgreSQL 18` 并执行演练。
- 生产环境 PostgreSQL 版本固定为 `18`。

## 验证清单

- 服务器外网不可直接访问 PostgreSQL 端口。
- Navicat 通过 `SSH Tunnel` 可稳定连接数据库并执行查询。
- 未通过 `Basic Auth` 无法访问 `/qiao-dash/` 与 `/admin-api/`。
- 通过 `Basic Auth` 后，后台仍需通过应用管理员登录鉴权。
- 腾讯云安全组公网入站仅保留 `SSH`、`80`、`443`。
- `ALLOWED_HOSTS` 不包含 `*`。

## 实施顺序

1. 调整 `staging` Compose，移除 PostgreSQL 端口映射。
2. 调整 Nginx，完成 `qiao-dash` 与 `admin-api` 的 `Basic Auth`。
3. 收敛 `staging` 环境变量中的主机白名单配置。
4. 执行连通性与鉴权验证。
5. 在开发环境执行 PostgreSQL 主版本升级测试并记录结论。
