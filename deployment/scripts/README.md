# 部署参考

## 首次部署

### 1) 本地打包（Windows）

```powershell
powershell.exe -ExecutionPolicy Bypass -File "deployment\scripts\pack-for-windows.ps1"
```

### 2) 上传产物

上传 `ailo-staging-deploy-YYYYMMDD-HHMMSS.tar.gz` 到服务器 `/home/ubuntu/`。

### 3) 服务器初始化（仅首次）

```bash
ssh ubuntu@ark3.qiaoqiaoai.cn
cd /home/ubuntu
tar -xzf ailo-staging-deploy-YYYYMMDD-HHMMSS.tar.gz
cd ailo/deployment/scripts
chmod +x setup.sh
./setup.sh
```

重新登录后执行：

```bash
ssh ubuntu@ark3.qiaoqiaoai.cn
sudo mkdir -p /opt/ailo-staging
sudo chown -R ubuntu:ubuntu /opt/ailo-staging
mv /home/ubuntu/ailo /opt/ailo-staging/
cd /opt/ailo-staging/ailo/deployment/scripts
chmod +x *.sh
./deploy.sh start
```

## 常规更新

先把 `ailo-staging-deploy-YYYYMMDD-HHMMSS.tar.gz` 上传到服务器 `/home/ubuntu/`，然后执行：

```bash
ssh ubuntu@ark3.qiaoqiaoai.cn
cd /opt/ailo-staging/ailo/deployment/scripts
sudo ./deploy.sh deploy --package /home/ubuntu/ailo-staging-deploy-YYYYMMDD-HHMMSS.tar.gz
```

`deploy --package` 包含代码备份、数据库备份、解压新包、替换代码目录、镜像重建、容器启动、数据库迁移。

## deploy.sh 命令

```bash
cd /opt/ailo-staging/ailo/deployment/scripts

./deploy.sh start
./deploy.sh stop
./deploy.sh restart
./deploy.sh deploy --package /home/ubuntu/ailo-staging-deploy-YYYYMMDD-HHMMSS.tar.gz
./deploy.sh update
./deploy.sh update --rebuild
./deploy.sh logs
./deploy.sh logs backend_staging
./deploy.sh status
./deploy.sh health
./deploy.sh backup
```

## 环境变量必填项

`/opt/ailo-staging/ailo/deployment/.env.staging` 必须包含：

- `WECHAT_APP_ID`
- `WECHAT_APP_SECRET`

## 发布后验证

```bash
cd /opt/ailo-staging/ailo/deployment/scripts
./deploy.sh status
./deploy.sh health
docker ps
```

- 管理后台：`https://ark3.qiaoqiaoai.cn/qiao-dash/`
- API：`https://ark3.qiaoqiaoai.cn/api/`

## 回滚参考

### 代码回滚

```bash
ls -lht /opt/ailo-staging/backups/code/ | head -5
cd /opt/ailo-staging
mv ailo ailo.failed.$(date +%Y%m%d-%H%M%S)
mkdir -p ailo
tar -xzf /opt/ailo-staging/backups/code/backup-YYYYMMDD-HHMMSS.tar.gz -C ailo
cd /opt/ailo-staging/ailo/deployment/scripts
./deploy.sh update --rebuild
```

### 数据库回滚

```bash
ls -lht /opt/ailo-staging/backups/database/ | head -5
gunzip -c /opt/ailo-staging/backups/database/db-YYYYMMDD-HHMMSS.sql.gz | docker exec -i postgres psql -U ailo_user ailo
```

## 关键路径与名称

- 项目路径：`/opt/ailo-staging/ailo/`
- 部署脚本：`/opt/ailo-staging/ailo/deployment/scripts/`
- 环境文件：`/opt/ailo-staging/ailo/deployment/.env.staging`
- 备份目录：`/opt/ailo-staging/backups/`
- 日志服务名：`backend_staging`、`nginx_staging`、`postgres_staging`
- 容器名：`backend`、`nginx`、`postgres`
