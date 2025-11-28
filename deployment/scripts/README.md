# Deployment Scripts

This directory contains scripts for deploying and managing the Says application in the test environment.

## Scripts Overview

### Local Scripts (Run on Development Machine)

#### pack-and-upload.sh
Packs the project and uploads it to the server.

```bash
# Full deployment
./pack-and-upload.sh --host YOUR_SERVER_IP

# Pack only (for manual upload via xftp)
./pack-and-upload.sh --pack-only

# Deploy with rebuild
./pack-and-upload.sh --host YOUR_SERVER_IP --rebuild

# Deploy without migration
./pack-and-upload.sh --host YOUR_SERVER_IP --no-migrate
```

### Server Scripts (Run on Server)

#### setup.sh
Initial server setup (run once).

```bash
# SSH to server first
ssh ubuntu@YOUR_SERVER_IP

# Run setup
cd /opt/says-test/says/deployment/scripts
chmod +x setup.sh
./setup.sh
```

#### deploy.sh
Deploy and manage services.

```bash
# Start services
./deploy.sh start

# Stop services
./deploy.sh stop

# Restart services
./deploy.sh restart

# Update services
./deploy.sh update

# Update with rebuild
./deploy.sh update --rebuild

# Update without migration
./deploy.sh update --no-migrate

# View logs
./deploy.sh logs
./deploy.sh logs backend_test

# Check status
./deploy.sh status

# Setup SSL
./deploy.sh ssl

# Backup
./deploy.sh backup
```

#### backup.sh
Backup code and database.

```bash
# Backup everything
./backup.sh all

# Backup code only
./backup.sh code

# Backup database only
./backup.sh database

# Show statistics
./backup.sh stats

# Clean old backups
./backup.sh clean
```

#### rollback.sh
Rollback to previous version.

```bash
# List available backups
./rollback.sh --list

# Rollback code
./rollback.sh --code

# Rollback database
./rollback.sh --database

# Rollback both
./rollback.sh --all

# Rollback to specific version
./rollback.sh --code --version 2

# Rollback migration
./rollback.sh --migration 1
```

## Quick Start

### First Time Deployment

1. **On local machine:**
```bash
cd deployment/scripts
chmod +x pack-and-upload.sh
./pack-and-upload.sh --pack-only
```

2. **Upload via xftp:**
   - Upload `says-test-deploy.tar.gz` to `/home/ubuntu/`

3. **On server:**
```bash
ssh ubuntu@YOUR_SERVER_IP
cd ~
tar -xzf says-test-deploy.tar.gz
cd says/deployment/scripts
chmod +x setup.sh
./setup.sh
# Log out and log back in
exit
ssh ubuntu@YOUR_SERVER_IP
sudo mkdir -p /opt/says-test
sudo chown -R ubuntu:ubuntu /opt/says-test
mv ~/says /opt/says-test/
cd /opt/says-test/says/deployment/scripts
chmod +x *.sh
./deploy.sh start
./deploy.sh ssl
```

### Updating Deployment

**On local machine:**
```bash
cd deployment/scripts
./pack-and-upload.sh --host YOUR_SERVER_IP
```

## Common Tasks

### View Logs
```bash
./deploy.sh logs backend_test
```

### Check Status
```bash
./deploy.sh status
```

### Backup
```bash
./backup.sh all
```

### Rollback
```bash
./rollback.sh --code
```

## Troubleshooting

### Permission Denied
```bash
chmod +x *.sh
```

### Docker Permission Issues
```bash
# Add user to docker group
sudo usermod -aG docker $USER
# Log out and log back in
```

### Services Not Starting
```bash
# Check logs
./deploy.sh logs

# Check Docker
docker ps -a

# Restart services
./deploy.sh restart
```

## Notes

- All scripts use color-coded output for better readability
- Backups are automatically managed (3 code backups, 7 days of database backups)
- Scripts include error handling and validation
- Use `--help` flag for detailed usage information

## See Also

- [Deployment Guide](../docs/deployment-guide.md)
- [Credentials](../docs/credentials.md) (not in git)
