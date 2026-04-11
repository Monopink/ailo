# Deployment Quick Guide

本文件包含通用打包、上传、部署与简单运维流程。环境差异见：
- deployment/staging/scripts/README.md
- deployment/prod/scripts/README.md

## Windows 打包

Staging:

```powershell
powershell.exe -ExecutionPolicy Bypass -File "deployment\staging\scripts\pack-for-windows.ps1"
```

Prod:

```powershell
powershell.exe -ExecutionPolicy Bypass -File "deployment\prod\scripts\pack-for-windows.ps1"
```

包名格式：
- ailo-staging-deploy-YYYYMMDD-HHMMSS.tar.gz
- ailo-prod-deploy-YYYYMMDD-HHMMSS.tar.gz

## 上传

上传到：

```text
/home/ubuntu/
```

## 部署

```bash
cd /opt/ailo-<env>/ailo/deployment/<env>/scripts
./deploy.sh deploy --package /home/ubuntu/<package>
```

## 常用运维

```bash
./deploy.sh start
./deploy.sh stop
./deploy.sh restart
./deploy.sh status
./deploy.sh health
./deploy.sh logs
./deploy.sh logs <service>
```

Dozzle（容器日志 UI，经 Nginx Basic Auth 保护）：

```text
https://<DOMAIN>/ops/logs/
```

## Nginx 网关模板

- Nginx 使用 `nginx/entrypoint.sh` 渲染模板到容器内 `default.conf`。
- 默认模板为 `nginx/conf.d/app.conf`。
- 可通过环境变量 `NGINX_TEMPLATE` 选择其它模板文件名。

## AI 失灵应急

代码回滚：

```bash
ls -lht /opt/ailo-<env>/backups/code/ | head -5
cd /opt/ailo-<env>
mv ailo ailo.failed.YYYYMMDD-HHMMSS
mkdir -p ailo
tar -xzf /opt/ailo-<env>/backups/code/backup-YYYYMMDD-HHMMSS.tar.gz -C ailo
cd /opt/ailo-<env>/ailo/deployment/<env>/scripts
./deploy.sh update --rebuild
```

数据库回滚：

```bash
ls -lht /opt/ailo-<env>/backups/database/ | head -5
gunzip -c /opt/ailo-<env>/backups/database/db-YYYYMMDD-HHMMSS.sql.gz | docker exec -i postgres psql -U ailo_user ailo
```
