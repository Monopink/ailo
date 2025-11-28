# 测试服务器部署流程

## 部署步骤

### 1. 打包项目（Windows）

```powershell
# 在项目根目录执行
powershell.exe -ExecutionPolicy Bypass -File "deployment\scripts\pack-for-windows.ps1"
```

输出文件：`says-test-deploy-YYYYMMDD-HHMMSS.tar.gz`

### 2. 上传文件

使用 xftp 上传到服务器：

- 本地：`D:\Polychrome\Code\Github\says\says-test-deploy-*.tar.gz`
- 服务器：`/home/ubuntu/`

### 3. 部署

```bash
ssh ubuntu@ark3.qiaoqiaoai.cn
cd /opt/says-test/says/deployment/scripts
sudo bash deploy.sh deploy --package /home/ubuntu/says-test-deploy-YYYYMMDD-HHMMSS.tar.gz
```

部署过程：

1. 备份代码和数据库
2. 停止服务
3. 解压新代码
4. 重建 Docker 镜像
5. 启动服务
6. 运行数据库迁移

耗时：2-3 分钟（首次 5-10 分钟）

### 3.1 环境变量必填项（.env.test）

以下键必须在 `deployment/.env.test` 中配置，否则后端将无法启动：

- `WECHAT_APP_ID`
- `WECHAT_APP_SECRET`

示例（测试环境可使用占位值）：

```
WECHAT_APP_ID=dummy-test-app-id
WECHAT_APP_SECRET=dummy-test-app-secret
```

脚本会在启动前校验以上必填项，缺失将直接报错并终止部署。

### 4. 验证

```bash
# 检查容器状态
docker ps

# 访问管理后台
# https://ark3.qiaoqiaoai.cn/qiao-dash/
# 用户名: admin
# 密码: admin123
```

---

## 常见问题

### 迁移失败

```bash
# 查看当前迁移版本
docker exec backend_test_container alembic current

# 手动运行迁移
docker exec backend_test_container alembic upgrade head
```

### 容器不健康

```bash
# 查看日志
docker logs backend_test_container --tail 100

# 重启容器
docker restart backend_test_container

提示：部署脚本的健康检查通过 Nginx 容器内网访问后端（backend_test_container:8000/health），不要直接用宿主机 8000 端口检查（未暴露）。
```

### 无法访问管理后台

```bash
# 检查 nginx
docker exec nginx_test_container nginx -t

# 检查后端
docker exec nginx_test_container curl -f http://backend_test:8000/health

# 重启 nginx
docker restart nginx_test_container
```

---

## 回滚

```bash
# 查看备份
ls -lht /opt/says-test/backups/code/ | head -5

# 回滚代码
cd /opt/says-test/says/deployment/scripts
sudo bash deploy.sh rollback --backup /opt/says-test/backups/code/backup-YYYYMMDD-HHMMSS.tar.gz

# 回滚数据库（如需要）
sudo bash deploy.sh restore-db --backup /opt/says-test/backups/database/db-YYYYMMDD-HHMMSS.sql.gz
```

---

## 维护命令

```bash
cd /opt/says-test/says/deployment/scripts

# 查看状态
sudo bash deploy.sh status

# 查看日志
sudo bash deploy.sh logs backend
sudo bash deploy.sh logs nginx
sudo bash deploy.sh logs postgres

# 重启服务
sudo bash deploy.sh restart

# 停止服务
sudo bash deploy.sh stop

# 启动服务
sudo bash deploy.sh start
```

---

## 快速参考

### 路径

```
项目根目录:    /opt/says-test/says/
备份目录:      /opt/says-test/backups/
脚本目录:      /opt/says-test/says/deployment/scripts/
环境配置:      /opt/says-test/says/deployment/.env.test
```

### URL

```
管理后台:      https://ark3.qiaoqiaoai.cn/qiao-dash/
API:          https://ark3.qiaoqiaoai.cn/api/
```

### 容器名称

```
backend_test_container
postgres_test_container
nginx_test_container
```

### 凭据

```
管理员:        admin / admin123
数据库:        postgres / says_test
```
