# Production Deployment (Admin)

通用流程见：deployment/README.md

## 环境信息

- 包名：ailo-prod-deploy-YYYYMMDD-HHMMSS.tar.gz
- 项目路径：/opt/ailo-prod/ailo/
- 脚本路径：/opt/ailo-prod/ailo/deployment/prod/scripts/
- 环境文件：/opt/ailo-prod/ailo/deployment/prod/.env
- Basic Auth：/opt/ailo-prod/ailo/deployment/prod/secrets/.htpasswd
- DB_HOST：postgres

## 首次初始化

```bash
cp /opt/ailo-prod/ailo/deployment/.env.example /opt/ailo-prod/ailo/deployment/.env
cp /opt/ailo-prod/ailo/deployment/prod/.env.example /opt/ailo-prod/ailo/deployment/prod/.env

cd /opt/ailo-prod/ailo/deployment/scripts
sudo ./generate-random-secrets.sh prod --basic-auth-user admin

cd /opt/ailo-prod/ailo/deployment/prod/scripts
./deploy.sh start
```

## 数据库备份（systemd timer）

安装备份脚本运行环境：

```bash
cd /opt/ailo-prod/ailo/deployment/prod/scripts
sudo ./setup-backup-venv.sh
```

如果提示 `ensurepip is not available`，说明系统缺少 python venv 支持，请先安装：

```bash
sudo apt-get update -y
sudo apt-get install -y python3.12-venv
```

安装并启用 systemd timer：

```bash
sudo cp /opt/ailo-prod/ailo/deployment/prod/systemd/ailo-db-backup.service /etc/systemd/system/
sudo cp /opt/ailo-prod/ailo/deployment/prod/systemd/ailo-db-backup.timer /etc/systemd/system/
sudo cp /opt/ailo-prod/ailo/deployment/prod/systemd/ailo-backup-jobs-cleanup.service /etc/systemd/system/
sudo cp /opt/ailo-prod/ailo/deployment/prod/systemd/ailo-backup-jobs-cleanup.timer /etc/systemd/system/

sudo systemctl daemon-reload
sudo systemctl enable --now ailo-db-backup.timer
sudo systemctl enable --now ailo-backup-jobs-cleanup.timer
```

手动执行一次备份（用于首次验证）：

```bash
sudo systemctl start ailo-db-backup.service
```

## fail2ban

```bash
cd /opt/ailo-prod/ailo/deployment/fail2ban
sudo ./setup-fail2ban.sh prod "127.0.0.1/8 ::1 <你的固定公网IP>"
```
