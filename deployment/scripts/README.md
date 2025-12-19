# Deployment Scripts

This directory contains simplified scripts for deploying and managing the application in the staging environment.

## Scripts Overview

### Local Scripts (Run on Development Machine)

#### pack-for-windows.ps1
Windows PowerShell script to pack the project for deployment.

```powershell
# Pack project
.\pack-for-windows.ps1
```

Creates a timestamped deployment package (e.g., `ailo-staging-deploy-20241218-143022.tar.gz`) in the project root.

#### pack-and-upload.sh
Linux/Mac script to pack, upload, and optionally deploy to the server.

```bash
# Full deployment (pack + upload + deploy)
./pack-and-upload.sh --host YOUR_SERVER_IP

# Pack only (for manual upload)
./pack-and-upload.sh --pack-only

# Upload existing package
./pack-and-upload.sh --upload-only --host YOUR_SERVER_IP

# Deploy with Docker rebuild
./pack-and-upload.sh --host YOUR_SERVER_IP --rebuild
```

### Server Scripts (Run on Server)

#### setup.sh
Initial server setup (run once on new server).

```bash
# SSH to server
ssh ubuntu@YOUR_SERVER_IP

# Run setup
cd /opt/ailo-staging/ailo/deployment/scripts
chmod +x setup.sh
./setup.sh
```

This script:
- Creates `/opt/ailo-staging` directory structure
- Installs docker-compose and required tools
- Configures Docker permissions
- Cleans up old containers

#### deploy.sh
All-in-one deployment and management script.

```bash
# Start services
./deploy.sh start

# Stop services
./deploy.sh stop

# Restart services
./deploy.sh restart

# Update services (with automatic backup)
./deploy.sh update

# Update with Docker image rebuild
./deploy.sh update --rebuild

# View logs (all services)
./deploy.sh logs

# View logs (specific service)
./deploy.sh logs backend_staging

# Check service status
./deploy.sh status

# Check service health
./deploy.sh health

# Manual backup (code + database)
./deploy.sh backup
```

## Quick Start

### First Time Deployment

**1. On local Windows machine:**
```powershell
cd deployment\scripts
.\pack-for-windows.ps1
```

**2. Upload via xftp:**
- Upload `ailo-staging-deploy-YYYYMMDD-HHMMSS.tar.gz` to `/home/ubuntu/`

**3. On server:**
```bash
# SSH to server
ssh ubuntu@YOUR_SERVER_IP

# Extract package
cd ~
tar -xzf ailo-staging-deploy-*.tar.gz

# Run initial setup
cd ailo/deployment/scripts
chmod +x setup.sh
./setup.sh

# Log out and back in (for Docker group permissions)
exit
ssh ubuntu@YOUR_SERVER_IP

# Move to deployment directory
sudo mkdir -p /opt/ailo-staging
sudo chown -R ubuntu:ubuntu /opt/ailo-staging
mv ~/ailo /opt/ailo-staging/

# Start services
cd /opt/ailo-staging/ailo/deployment/scripts
chmod +x *.sh
./deploy.sh start
```

### Subsequent Updates

**On local machine:**
```bash
cd deployment/scripts
./pack-and-upload.sh --host YOUR_SERVER_IP
```

Or manually:
1. Pack with `pack-for-windows.ps1` (Windows) or `pack-and-upload.sh --pack-only` (Linux/Mac)
2. Upload package to server via xftp
3. SSH to server and run: `cd /opt/ailo-staging/ailo/deployment/scripts && ./deploy.sh update`

## Common Tasks

### View Real-time Logs
```bash
# All services
./deploy.sh logs

# Specific service
./deploy.sh logs backend_staging
./deploy.sh logs postgres_staging
./deploy.sh logs nginx_staging
```

### Check System Status
```bash
# Service status and resource usage
./deploy.sh status

# Health check
./deploy.sh health
```

### Backup
```bash
# Manual backup (code + database)
./deploy.sh backup
```

Backups are stored in `/opt/ailo-staging/backups/`:
- Code backups: Last 3 versions
- Database backups: Last 7 days

Automatic backups are created during `./deploy.sh update`.

## Troubleshooting

### Permission Denied
```bash
chmod +x *.sh
```

### Docker Permission Issues
```bash
# Add user to docker group
sudo usermod -aG docker $USER

# Log out and log back in for changes to take effect
exit
```

### Services Not Starting
```bash
# Check logs for errors
./deploy.sh logs

# Check container status
docker ps -a

# Check Docker Compose configuration
cd /opt/ailo-staging/ailo/deployment
docker-compose -f docker-compose.staging.yml config

# Restart services
./deploy.sh restart
```

### Database Connection Issues
```bash
# Check PostgreSQL container
./deploy.sh logs postgres_staging

# Check environment variables
cat /opt/ailo-staging/ailo/deployment/.env.staging
```

## File Locations

- **Project:** `/opt/ailo-staging/ailo/`
- **Docker Compose:** `/opt/ailo-staging/ailo/deployment/docker-compose.staging.yml`
- **Environment:** `/opt/ailo-staging/ailo/deployment/.env.staging`
- **Backups:** `/opt/ailo-staging/backups/`
- **Scripts:** `/opt/ailo-staging/ailo/deployment/scripts/`

## Notes

- All scripts use color-coded output for better readability
- Scripts are hardcoded for staging environment only
- Backups are automatically created during updates
- No backward compatibility with old test environment
- Database migrations run automatically during updates

## See Also

- [Deployment Guide](../docs/deployment-guide.md)
- [Quick Deployment Guide](../docs/quick-deployment-guide.md)
