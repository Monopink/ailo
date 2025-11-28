#!/bin/bash
# Server Setup Script for Test Environment
# This script should be run once on the server for initial setup

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    log_error "Please do not run this script as root"
    exit 1
fi

log_info "Starting server setup for test environment..."

# Step 1: Clean up old Docker resources
log_info "Cleaning up old Docker resources..."

# Stop and remove old containers
if sudo docker ps -a | grep -q "says"; then
    log_info "Stopping old containers..."
    sudo docker stop $(sudo docker ps -a | grep "says" | awk '{print $1}') 2>/dev/null || true
    sudo docker rm $(sudo docker ps -a | grep "says" | awk '{print $1}') 2>/dev/null || true
fi

# Remove old images (MySQL, old versions)
log_info "Removing old Docker images..."
sudo docker rmi mysql:8.0 2>/dev/null || true
sudo docker rmi node:latest 2>/dev/null || true

# Remove old volumes
log_info "Removing old Docker volumes..."
sudo docker volume rm says_mysql_data 2>/dev/null || true
sudo docker volume rm says_certbot_certs 2>/dev/null || true
sudo docker volume rm says_certbot_webroot 2>/dev/null || true

log_success "Docker cleanup completed"

# Step 2: Configure Docker permissions
log_info "Configuring Docker permissions..."
if ! groups $USER | grep -q docker; then
    sudo usermod -aG docker $USER
    log_success "Added $USER to docker group"
    log_warning "You need to log out and log back in for group changes to take effect"
    log_warning "Or run: newgrp docker"
else
    log_info "User already in docker group"
fi

# Step 3: Create directory structure
log_info "Creating directory structure..."
sudo mkdir -p /opt/says-test/{logs,backups/{code,database}}
sudo chown -R $USER:$USER /opt/says-test
log_success "Directory structure created"

# Step 4: Install required tools
log_info "Checking required tools..."

# Check if docker-compose is installed
if ! command -v docker-compose &> /dev/null; then
    log_warning "docker-compose not found, installing..."
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
    log_success "docker-compose installed"
else
    log_info "docker-compose already installed"
fi

# Check if curl is installed
if ! command -v curl &> /dev/null; then
    log_warning "curl not found, installing..."
    sudo apt-get update
    sudo apt-get install -y curl
    log_success "curl installed"
else
    log_info "curl already installed"
fi

# Step 5: System information
log_info "System information:"
echo "  OS: $(lsb_release -d | cut -f2)"
echo "  Kernel: $(uname -r)"
echo "  Memory: $(free -h | awk '/^Mem:/ {print $2}')"
echo "  Disk: $(df -h / | awk 'NR==2 {print $2}')"
echo "  Docker: $(docker --version)"
echo "  Docker Compose: $(docker-compose --version)"

# Step 6: Verify setup
log_info "Verifying setup..."

# Check Docker service
if sudo systemctl is-active --quiet docker; then
    log_success "Docker service is running"
else
    log_error "Docker service is not running"
    exit 1
fi

# Check directory permissions
if [ -w "/opt/says-test" ]; then
    log_success "Directory permissions are correct"
else
    log_error "Cannot write to /opt/says-test"
    exit 1
fi

log_success "Server setup completed successfully!"
log_info ""
log_info "Next steps:"
log_info "1. Upload project files to /home/$USER/"
log_info "2. Extract: tar -xzf says-test-deploy.tar.gz"
log_info "3. Move to /opt/says-test/: mv says /opt/says-test/"
log_info "4. Run deploy script: cd /opt/says-test/says/deployment/scripts && ./deploy.sh test start"
log_info ""
log_warning "If you added user to docker group, please log out and log back in"
