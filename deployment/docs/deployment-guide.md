# Test Environment Deployment Guide

## Overview

This guide covers the deployment of the Says application to the test environment on Tencent Cloud.

**Environment Details:**

- Domain: ark3.qiaoqiaoai.cn
- Server: Ubuntu 22.04, 2GB RAM, 40GB Disk
- Services: PostgreSQL, FastAPI Backend, Nginx, Certbot

---

## Prerequisites

### Local Machine

- Bash shell (Linux/macOS/WSL)
- SSH access to server
- xftp (optional, for manual file transfer)

### Server

- Ubuntu 22.04 or later
- Docker and Docker Compose installed
- Ports 80, 443 open in firewall (configured in Tencent Cloud panel)

---

## Initial Deployment

### Step 1: Prepare Configuration

1. Copy environment template:

```bash
cd deployment
cp .env.test.example .env.test
```

2. Edit `.env.test` with actual values:

```bash
# Database password
POSTGRES_PASSWORD=SaysTest2025!Pg#Secure$789

# JWT secret
JWT_SECRET_KEY=a7f3e9d2c8b4f1a6e5d9c3b7f2a8e4d1c9b5f3a7e2d8c4b1f6a9e5d2c8b4f1a6

# Admin secret
ADMIN_SECRET_KEY=b8e4f1d3c9a5f2b7e6d1c4b8f3a9e5d2c1b6f4a8e3d9c5b2f7a1e6d3c9b5f2a7

# SSL email
CERTBOT_EMAIL=cacti-idly-finale@duck.com
```

### Step 2: Pack and Upload

**Option A: Automated (Recommended)**

```bash
cd deployment/scripts
chmod +x pack-and-upload.sh
./pack-and-upload.sh --host YOUR_SERVER_IP
```

**Option B: Manual with xftp**

```bash
# Pack only
cd deployment/scripts
chmod +x pack-and-upload.sh
./pack-and-upload.sh --pack-only

# Upload says-test-deploy.tar.gz using xftp to /home/ubuntu/
```

### Step 3: Server Setup (First Time Only)

SSH to server and run setup script:

```bash
ssh ubuntu@YOUR_SERVER_IP

# Extract package
cd ~
tar -xzf says-test-deploy.tar.gz

# Run setup script
cd says/deployment/scripts
chmod +x setup.sh
./setup.sh

# Log out and log back in for docker group to take effect
exit
ssh ubuntu@YOUR_SERVER_IP
```

### Step 4: Deploy Application

```bash
# Move project to /opt
sudo mkdir -p /opt/says-test
sudo chown -R ubuntu:ubuntu /opt/says-test
mv ~/says /opt/says-test/

# Copy .env.test to server
# (Upload via xftp or create manually)

# Deploy
cd /opt/says-test/says/deployment/scripts
chmod +x *.sh
./deploy.sh start
```

### Step 5: Setup SSL Certificate

**Note:** Certificate is already obtained for ark3.qiaoqiaoai.cn. Skip this step if certificate exists.

For manual certificate renewal (when needed):

```bash
docker run --rm \
  -v certbot_webroot:/var/www/certbot \
  -v /etc/letsencrypt:/etc/letsencrypt \
  certbot/certbot renew
```

### Step 6: Verify Deployment

1. Check service status:

```bash
./deploy.sh status
```

2. Check logs:

```bash
./deploy.sh logs backend_test
```

3. Access admin panel:

```
https://ark3.qiaoqiaoai.cn/qiao-dash/
Username: admin
Password: admin123
```

---

## Updating Deployment

### Standard Update Process (Recommended)

This is the recommended way to deploy new code changes:

**Step 1: Pack on Local Machine (Windows)**

```powershell
# In PowerShell
cd deployment\scripts
.\pack-for-windows.ps1
# Output: says-test-deploy-YYYYMMDD-HHMMSS.tar.gz
```

**Step 2: Upload to Server**

- Use xftp to upload the .tar.gz file to `/home/ubuntu/`

**Step 3: Deploy on Server**

```bash
ssh ubuntu@YOUR_SERVER_IP
cd /opt/says-test/says/deployment/scripts
sudo ./deploy.sh deploy --package /home/ubuntu/says-test-deploy-YYYYMMDD-HHMMSS.tar.gz
```

The deploy command will automatically:

- Backup current code and database
- Stop services
- Extract and copy new files
- Preserve .env.test configuration
- Check and fix .env.test completeness (e.g., add REDIS_URL if missing)
- Remove conflicting files (e.g., default.conf)
- Rebuild Docker images
- Start services
- Run database migrations
- Check service health

### Quick Update (Code Changes Only, No Rebuild)

If you only changed code without modifying Dockerfile or dependencies:

```bash
# On server
cd /opt/says-test/says/deployment/scripts
sudo ./deploy.sh update
```

### Update with Full Rebuild

```bash
# On server
cd /opt/says-test/says/deployment/scripts
sudo ./deploy.sh update --rebuild
```

### Update without Migration

```bash
# On server
cd /opt/says-test/says/deployment/scripts
sudo ./deploy.sh update --rebuild --no-migrate
```

---

## Database Management

### Run Migrations

```bash
# On server
cd /opt/says-test/says/deployment/scripts
./deploy.sh update  # Migrations run automatically
```

### Rollback Migration

```bash
# Rollback last migration
./rollback.sh --migration 1

# Rollback 2 migrations
./rollback.sh --migration 2
```

### Manual Migration

```bash
# Check current version
docker exec backend_test_container alembic current

# Upgrade to latest
docker exec backend_test_container alembic upgrade head

# Downgrade one version
docker exec backend_test_container alembic downgrade -1
```

---

## Backup and Restore

### Manual Backup

```bash
cd /opt/says-test/says/deployment/scripts
./backup.sh all
```

### Automatic Backup (Cron)

Add to crontab:

```bash
crontab -e

# Add this line for daily backup at 2 AM
0 2 * * * /opt/says-test/says/deployment/scripts/backup.sh all
```

### Restore from Backup

```bash
# List available backups
./rollback.sh --list

# Rollback code to last backup
./rollback.sh --code

# Rollback database to last backup
./rollback.sh --database

# Rollback both
./rollback.sh --all
```

---

## Monitoring and Maintenance

### View Logs

```bash
# All services
./deploy.sh logs

# Specific service
./deploy.sh logs backend_test
./deploy.sh logs nginx_test
./deploy.sh logs postgres_test

# Follow logs
docker logs -f backend_test_container
```

### Check Service Status

```bash
./deploy.sh status
```

### Check Resource Usage

```bash
docker stats
```

### Restart Services

```bash
# Restart all
./deploy.sh restart

# Restart specific service
docker restart backend_test_container
```

---

## Troubleshooting

### Services Not Starting

1. Check logs:

```bash
./deploy.sh logs
```

2. Check Docker status:

```bash
docker ps -a
```

3. Check disk space:

```bash
df -h
```

### SSL Certificate Issues

1. Check Nginx logs:

```bash
docker logs nginx_test_container
```

2. Verify DNS:

```bash
nslookup ark3.qiaoqiaoai.cn
```

3. Manually request certificate:

```bash
docker-compose -f deployment/docker-compose.test.yml run --rm certbot_test
```

### Database Connection Issues

1. Check PostgreSQL logs:

```bash
docker logs postgres_test_container
```

2. Test connection:

```bash
docker exec postgres_test_container psql -U says_admin -d says_test -c "SELECT 1"
```

### Backend Not Responding

1. Check backend logs:

```bash
docker logs backend_test_container
```

2. Check health endpoint:

```bash
curl http://localhost:8000/health
```

3. Restart backend:

```bash
docker restart backend_test_container
```

---

## Common Tasks

### Update Environment Variables

1. Edit `.env.test` on server
2. Restart services:

```bash
./deploy.sh restart
```

### Clean Up Docker Resources

```bash
# Remove unused images
docker image prune -a

# Remove unused volumes
docker volume prune

# Remove unused networks
docker network prune
```

---

## Troubleshooting

### Database Schema Mismatch

**Problem:** Backend logs show errors like `column "is_active" does not exist`

**Cause:** Local database schema doesn't match the code

**Solution:**

```bash
# Option 1: Reinitialize local database
cd deployment
docker-compose down -v  # Remove volumes
docker-compose up -d    # Recreate with fresh schema

# Option 2: Run migrations
docker exec backend_container python migrate.py upgrade
```

### Nginx Fails to Start

**Problem:** Nginx container exits with "host not found in upstream"

**Cause:** Old `default.conf` file conflicts with `test.conf`

**Solution:**

```bash
# Remove conflicting config
sudo rm /opt/says-test/says/nginx/conf.d/default.conf
sudo docker restart nginx_test_container
```

### Missing Environment Variables

**Problem:** Backend fails to start with missing configuration errors

**Cause:** `.env.test` file is incomplete

**Solution:**

```bash
# Check for missing variables
cd /opt/says-test/says/deployment
diff .env.test.example .env.test

# Add missing variables (e.g., REDIS_URL)
echo "REDIS_URL=redis://localhost:6379/0" >> .env.test

# Recreate containers to apply changes
cd scripts
sudo ./deploy.sh stop
sudo ./deploy.sh start
```

### Deployment Package Structure Issues

**Problem:** After extracting package, files are in wrong location

**Cause:** Old version of pack-for-windows.ps1 created extra directory layer

**Solution:**

- Use the updated pack-for-windows.ps1 script
- Or use the new `deploy.sh deploy` command which handles this automatically

### Services Not Updating After Code Changes

**Problem:** Code changes don't appear after deployment

**Cause:** Docker images not rebuilt

**Solution:**

```bash
# Use deploy command (automatically rebuilds)
sudo ./deploy.sh deploy --package /path/to/package.tar.gz

# Or force rebuild with update command
sudo ./deploy.sh update --rebuild
```

### View Backup Statistics

```bash
./backup.sh stats
```

### Clean Old Backups

```bash
./backup.sh clean
```

---

## Security Notes

1. **Never commit `.env.test` to git**
2. **Keep backups secure**
3. **Regularly update Docker images**
4. **Monitor logs for suspicious activity**
5. **Use strong passwords for database and admin**

---

## Support

For issues or questions:

1. Check logs first
2. Review this guide
3. Check project documentation in `/docs`
4. Contact development team

---

## Quick Reference

```bash
# Deploy
./deploy.sh start

# Update
./pack-and-upload.sh --host SERVER_IP

# Backup
./backup.sh all

# Rollback
./rollback.sh --code

# Logs
./deploy.sh logs backend_test

# Status
./deploy.sh status
```
