# 敲敲AI聊天应用 - 完整部署指南

## 项目概述

敲敲AI聊天应用是一个基于微服务架构的现代化聊天应用，包含：

### 后端服务

- `accounts_service` - 用户账户管理服务 (端口8001)
- `contacts_service` - 联系人管理服务 (端口8002)
- `bot_message_service` - 机器人消息服务 (端口8003)

### 前端应用

- Vue 3 + Vite 单页应用，支持PWA功能 (端口5173)

### 基础设施

- MySQL 8.0 数据库 (端口33061)
- Nginx 反向代理 (生产环境)
- LeanCloud 即时通讯服务
- 豆包AI服务

本项目采用源码部署方式，通过Docker容器化运行。

## 环境准备

### 服务器要求

- Ubuntu 20.04+ 或 CentOS 7+
- 2GB+ 内存
- 10GB+ 磁盘空间
- 公网IP和域名

### 安装Docker环境

```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# 安装Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# 启动Docker并加入用户组
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker $USER

# 重新登录使权限生效
exit
```

### 配置防火墙

```bash
sudo ufw allow 22    # SSH
sudo ufw allow 80    # HTTP
sudo ufw allow 443   # HTTPS
sudo ufw enable
```

### 创建项目目录

```bash
mkdir -p ~/says
cd ~/says
```

## 上传项目代码

### 使用XFTP上传

1. **连接设置**：
   - 主机：服务器IP地址
   - 端口：22
   - 用户名：服务器用户名
   - 密码：服务器密码

2. **上传文件**：
   将本地项目的所有文件上传到服务器的 `~/says/` 目录

3. **必须上传的文件**：
   - `backend/.env.prod` - 生产环境配置
   - `deployment/docker-compose.prod.yml` - 容器编排配置
   - `deployment/deploy.sh` - 部署脚本
   - `backend/` - 后端服务代码
   - `frontend/` - 前端代码
   - `nginx/` - Nginx配置

## 部署步骤

### 1. 设置权限

```bash
cd ~/says
chmod +x deploy.sh renew-ssl.sh
```

### 2. 检查配置

```bash
# 检查环境变量文件
cat backend/.env.prod

# 检查Docker Compose配置
cat deployment/docker-compose.prod.yml
```

### 3. 初始化部署

```bash
# 初始化部署（构建镜像并启动服务）
./deploy.sh init
```

这个过程会：

- 构建所有服务的Docker镜像（约10-15分钟）
- 启动MySQL数据库
- 启动后端服务
- 启动前端服务
- 启动Nginx反向代理

### 4. 设置SSL证书

```bash
# 等待服务完全启动后执行
./deploy.sh ssl
```

## 验证部署

### 检查服务状态

```bash
./deploy.sh status
```

### 测试网站访问

```bash
# 测试HTTP重定向
curl -I http://web4.qiaoqiaoai.cn

# 测试HTTPS访问
curl -I https://web4.qiaoqiaoai.cn
```

### 浏览器访问

打开浏览器访问：`https://web4.qiaoqiaoai.cn`

## 常用管理命令

### 使用部署脚本（推荐）

```bash
# 启动所有服务
./deploy.sh start

# 停止所有服务
./deploy.sh stop

# 重启所有服务
./deploy.sh restart

# 查看服务状态
./deploy.sh status

# 查看所有服务日志
./deploy.sh logs

# 查看特定服务日志
./deploy.sh logs nginx
./deploy.sh logs accounts_service

# 更新部署（重新构建并重启）
./deploy.sh update

# 设置SSL证书
./deploy.sh ssl
```

### 基础Docker命令

```bash
# 进入deployment目录
cd deployment

# 启动服务
docker-compose -f docker-compose.prod.yml up -d

# 停止服务
docker-compose -f docker-compose.prod.yml down

# 重启服务
docker-compose -f docker-compose.prod.yml restart

# 查看服务状态
docker-compose -f docker-compose.prod.yml ps

# 查看日志
docker-compose -f docker-compose.prod.yml logs -f

# 重新构建并启动
docker-compose -f docker-compose.prod.yml up -d --build

# 查看特定服务日志
docker-compose -f docker-compose.prod.yml logs -f nginx

# 进入容器调试
docker-compose -f docker-compose.prod.yml exec accounts_service bash

# 清理未使用的镜像
docker image prune -f

# 清理所有未使用的资源
docker system prune -f
```

## 更新代码流程

1. **本地修改代码**
2. **重新上传到服务器**（使用XFTP覆盖文件）
3. **更新部署**：

   ```bash
   cd ~/says
   ./deploy.sh update
   ```

## SSL证书自动续期

```bash
# 编辑定时任务
crontab -e

# 添加以下行（每天凌晨2点检查续期）
0 2 * * * /home/用户名/says/renew-ssl.sh
```

## 故障排查

### 构建失败

```bash
# 进入deployment目录并查看详细构建日志
cd deployment
docker-compose -f docker-compose.prod.yml build --no-cache

# 清理Docker缓存
docker system prune -f
```

### 服务启动失败

```bash
# 查看详细错误日志
./deploy.sh logs [service_name]

# 检查容器状态
docker ps -a
```

### SSL证书申请失败

确认：

- 域名解析正确指向服务器
- 防火墙端口80和443已开放
- 没有其他服务占用这些端口

### 数据库连接问题

```bash
# 检查数据库状态
./deploy.sh logs mysql_db

# 测试数据库连接
cd deployment
docker-compose -f docker-compose.prod.yml exec mysql_db mysql -u says_user -p
```

## 备份重要数据

```bash
# 备份数据库
cd deployment
docker-compose -f docker-compose.prod.yml exec mysql_db mysqldump -u root -p says_db > ~/backup_$(date +%Y%m%d).sql

# 备份配置文件
cp ../backend/.env.prod ../backend/.env.prod.backup
cp docker-compose.prod.yml docker-compose.prod.yml.backup
```

## 环境配置说明

### 后端配置文件

- `backend/.env` - 开发环境配置
- `backend/.env.prod` - 生产环境配置  
- `backend/.env.staging` - 测试环境配置

### 前端配置文件

- `frontend/web/.env.development` - 开发环境配置
- `frontend/web/.env.production` - 生产环境配置
- `frontend/web/.env.staging` - 测试环境配置

### 服务端口

**生产环境**：

- 所有后端服务通过Nginx代理，不直接暴露端口
- MySQL: 3306 (支持外部访问)
- HTTP: 80 (自动重定向到HTTPS)
- HTTPS: 443 (主要访问端口)

**开发环境**：

- accounts_service: 8001
- contacts_service: 8002
- bot_message_service: 8003
- frontend: 5173
- MySQL: 33061

## 日志管理

### 日志位置

所有服务的日志都统一存储在 `./logs/` 目录下：

```
logs/
├── accounts_service/        # 账户服务日志
├── contacts_service/        # 联系人服务日志
├── bot_message_service/     # 消息服务日志
└── monitor.log             # 监控脚本日志
```

### 查看日志

```bash
# 查看实时日志
./deploy.sh logs

# 查看特定服务日志
./deploy.sh logs accounts_service

# 查看日志文件
tail -f logs/accounts_service/accounts_service.log

# 查看监控日志
tail -f logs/monitor.log
```

### 日志轮转

建议配置logrotate进行日志轮转：

```bash
# 创建logrotate配置
sudo tee /etc/logrotate.d/says-app > /dev/null <<EOF
/home/用户名/says/logs/*/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 644 root root
}
EOF
```

## 监控系统

### 健康检查

```bash
# 运行健康检查
./monitor.sh check

# 测试通知功能
./monitor.sh webhook-test
```

### 自动监控

设置定时任务进行自动监控：

```bash
# 编辑定时任务
crontab -e

# 添加监控任务（每5分钟检查一次）
*/5 * * * * /home/用户名/says/monitor.sh check
```

### 通知配置

在 `monitor.sh` 中设置 `WEBHOOK_URL` 变量来启用通知：

```bash
# 钉钉机器人示例
WEBHOOK_URL="https://oapi.dingtalk.com/robot/send?access_token=YOUR_TOKEN"

# 企业微信机器人示例
WEBHOOK_URL="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_KEY"
```

## 注意事项

1. **环境变量**：
   - 不要将敏感信息提交到版本控制
   - 生产环境使用强密码
   - 定期更新密钥

2. **安全**：
   - 定期更新系统和Docker
   - 监控服务日志
   - 限制网络访问

3. **备份**：
   - 定期备份数据库
   - 保留重要配置文件
   - 测试恢复流程

4. **日志**：
   - 定期清理旧日志文件
   - 监控磁盘空间使用
   - 配置日志轮转策略
