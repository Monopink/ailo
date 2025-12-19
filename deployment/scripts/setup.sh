#!/bin/bash
# Server Setup Script for Staging Environment
# Run once on server for initial setup
# Usage: ./setup.sh

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    log_error "Please do not run this script as root"
    exit 1
fi

BASE_DIR="/opt/ailo-staging"

log_info "Starting server setup for staging environment..."
log_info "Base directory: $BASE_DIR"

# Clean up old Docker resources
log_info "Cleaning up old Docker resources..."
if sudo docker ps -a | grep -q "ailo"; then
    log_info "Stopping old containers..."
    sudo docker stop $(sudo docker ps -a | grep "ailo" | awk '{print $1}') 2>/dev/null || true
    sudo docker rm $(sudo docker ps -a | grep "ailo" | awk '{print $1}') 2>/dev/null || true
fi

log_info "Removing old Docker images..."
sudo docker rmi mysql:8.0 2>/dev/null || true
sudo docker rmi node:latest 2>/dev/null || true

log_success "Docker cleanup completed"

# Configure Docker permissions
log_info "Configuring Docker permissions..."
if ! groups $USER | grep -q docker; then
    sudo usermod -aG docker $USER
    log_success "Added $USER to docker group"
    log_warning "You need to log out and log back in for group changes to take effect"
else
    log_info "User already in docker group"
fi

# Create directory structure
log_info "Creating directory structure..."
sudo mkdir -p ${BASE_DIR}/{logs,backups/{code,database}}
sudo chown -R $USER:$USER ${BASE_DIR}
log_success "Directory structure created at $BASE_DIR"

# Install required tools
log_info "Checking required tools..."

if ! command -v docker-compose &> /dev/null; then
    log_warning "docker-compose not found, installing..."
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
    log_success "docker-compose installed"
else
    log_info "docker-compose already installed"
fi

if ! command -v curl &> /dev/null; then
    log_warning "curl not found, installing..."
    sudo apt-get update && sudo apt-get install -y curl
    log_success "curl installed"
else
    log_info "curl already installed"
fi

if ! command -v rsync &> /dev/null; then
    log_warning "rsync not found, installing..."
    sudo apt-get update && sudo apt-get install -y rsync
    log_success "rsync installed"
else
    log_info "rsync already installed"
fi

# System information
log_info "System information:"
echo "  OS: $(lsb_release -d | cut -f2)"
echo "  Kernel: $(uname -r)"
echo "  Memory: $(free -h | awk '/^Mem:/ {print $2}')"
echo "  Disk: $(df -h / | awk 'NR==2 {print $2}')"
echo "  Docker: $(docker --version)"
echo "  Docker Compose: $(docker-compose --version)"

# Verify setup
log_info "Verifying setup..."

if sudo systemctl is-active --quiet docker; then
    log_success "Docker service is running"
else
    log_error "Docker service is not running"
    exit 1
fi

if [ -w "$BASE_DIR" ]; then
    log_success "Directory permissions are correct"
else
    log_error "Cannot write to $BASE_DIR"
    exit 1
fi

log_success "Server setup completed successfully!"
echo ""
log_info "Next steps:"
log_info "1. Upload deployment package to /home/$USER/"
log_info "2. Extract: tar -xzf ailo-staging-deploy-YYYYMMDD-HHMMSS.tar.gz"
log_info "3. Move to $BASE_DIR/: mv ailo $BASE_DIR/"
log_info "4. Configure .env.staging in $BASE_DIR/ailo/deployment/"
log_info "5. Run: cd $BASE_DIR/ailo/deployment/scripts && ./deploy.sh start"
echo ""
log_warning "If you added user to docker group, please log out and log back in"
