# Staging Deployment (Admin)

通用流程见：deployment/scripts/README.md

## 环境信息

- 包名：ailo-staging-deploy-YYYYMMDD-HHMMSS.tar.gz
- 项目路径：/opt/ailo-staging/ailo/
- 脚本路径：/opt/ailo-staging/ailo/deployment/staging/scripts/
- 环境文件：/opt/ailo-staging/ailo/deployment/staging/.env
- Basic Auth：/opt/ailo-staging/ailo/deployment/staging/secrets/.htpasswd
- Logs Basic Auth：/opt/ailo-staging/ailo/deployment/staging/secrets/.htpasswd_logs
- DB_HOST：postgres
- Dozzle：`https://<DOMAIN>/ops/logs/`

## 首次初始化

```bash
ssh ubuntu@ark3.qiaoqiaoai.cn
cd /opt/ailo-staging/ailo/deployment/staging/scripts
chmod +x setup.sh
./setup.sh

cp /opt/ailo-staging/ailo/deployment/.env.example /opt/ailo-staging/ailo/deployment/.env
cp /opt/ailo-staging/ailo/deployment/staging/.env.example /opt/ailo-staging/ailo/deployment/staging/.env

cd /opt/ailo-staging/ailo/deployment/scripts
./generate-basic-auth.sh staging admin
./generate-basic-auth.sh staging logs_admin --target logs

cd /opt/ailo-staging/ailo/deployment/staging/scripts
./deploy.sh start
```

## fail2ban

```bash
cd /opt/ailo-staging/ailo/deployment/fail2ban
sudo ./setup-fail2ban.sh staging "127.0.0.1/8 ::1 <你的固定公网IP>"
```
