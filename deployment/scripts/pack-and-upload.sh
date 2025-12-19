#!/bin/bash
# Pack and Upload Script for Staging Environment
# Run on local machine
# Usage: ./pack-and-upload.sh [options]

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
DEPLOY_PACKAGE="ailo-staging-deploy-${TIMESTAMP}.tar.gz"
SERVER_USER="${SERVER_USER:-ubuntu}"
SERVER_HOST=""
SERVER_PATH="/home/$SERVER_USER"

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Get server host
get_server_host() {
    if [ -z "$SERVER_HOST" ]; then
        read -p "Enter server IP or hostname: " SERVER_HOST
    fi
    if [ -z "$SERVER_HOST" ]; then
        log_error "Server host is required"
        exit 1
    fi
}

# Pack project
pack_project() {
    log_info "Packing project for staging environment..."
    cd "$PROJECT_ROOT"

    local temp_dir=$(mktemp -d)
    local pack_dir="$temp_dir/ailo"
    mkdir -p "$pack_dir"

    log_info "Copying files..."
    cp -r backend "$pack_dir/"
    cp -r deployment "$pack_dir/"
    cp -r nginx "$pack_dir/"

    log_info "Cleaning up..."
    find "$pack_dir" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find "$pack_dir" -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
    find "$pack_dir" -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
    find "$pack_dir" -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
    find "$pack_dir" -type f -name "*.pyc" -delete 2>/dev/null || true
    find "$pack_dir" -type f -name "*.log" -delete 2>/dev/null || true
    find "$pack_dir" -type d -name "logs" -exec rm -rf {} + 2>/dev/null || true
    find "$pack_dir" -type d -name ".git" -exec rm -rf {} + 2>/dev/null || true
    rm -rf "$pack_dir/backend/venv" 2>/dev/null || true
    rm -rf "$pack_dir/deployment/.env"* 2>/dev/null || true

    log_info "Creating archive..."
    cd "$temp_dir"
    tar -czf "$DEPLOY_PACKAGE" ailo/
    mv "$DEPLOY_PACKAGE" "$PROJECT_ROOT/"
    rm -rf "$temp_dir"

    local size=$(du -h "$PROJECT_ROOT/$DEPLOY_PACKAGE" | cut -f1)
    log_success "Package created: $DEPLOY_PACKAGE ($size)"
}

# Upload to server
upload_to_server() {
    log_info "Uploading to server..."
    get_server_host

    if [ ! -f "$PROJECT_ROOT/$DEPLOY_PACKAGE" ]; then
        log_error "Package not found: $DEPLOY_PACKAGE"
        exit 1
    fi

    log_info "Uploading to $SERVER_USER@$SERVER_HOST:$SERVER_PATH..."
    scp "$PROJECT_ROOT/$DEPLOY_PACKAGE" "$SERVER_USER@$SERVER_HOST:$SERVER_PATH/"
    log_success "Package uploaded successfully"
}

# Deploy on server
deploy_on_server() {
    local rebuild=${1:-false}
    log_info "Deploying on server..."
    get_server_host

    local ssh_cmd="ssh $SERVER_USER@$SERVER_HOST"

    log_info "Extracting package..."
    $ssh_cmd "cd $SERVER_PATH && tar -xzf $DEPLOY_PACKAGE"

    log_info "Moving files to /opt/ailo-staging..."
    $ssh_cmd "sudo mkdir -p /opt/ailo-staging && sudo chown -R $SERVER_USER:$SERVER_USER /opt/ailo-staging"
    $ssh_cmd "rm -rf /opt/ailo-staging/ailo && mv $SERVER_PATH/ailo /opt/ailo-staging/"

    log_info "Running deployment..."
    local deploy_opts=""
    if [ "$rebuild" = true ]; then
        deploy_opts="--rebuild"
    fi

    $ssh_cmd "cd /opt/ailo-staging/ailo/deployment/scripts && chmod +x *.sh && ./deploy.sh update $deploy_opts"
    log_success "Deployment completed"
}

# Show usage
show_usage() {
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  --host HOST        Server hostname or IP"
    echo "  --pack-only        Only pack, don't upload"
    echo "  --upload-only      Only upload, don't deploy"
    echo "  --rebuild          Rebuild Docker images"
    echo "  --help             Show this help"
    echo ""
    echo "Examples:"
    echo "  $0                           # Pack, upload and deploy"
    echo "  $0 --host 1.2.3.4            # Specify server"
    echo "  $0 --pack-only               # Only create package"
    echo "  $0 --rebuild                 # Deploy with rebuild"
}

# Main logic
PACK_ONLY=false
UPLOAD_ONLY=false
REBUILD=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --host) SERVER_HOST=$2; shift 2 ;;
        --pack-only) PACK_ONLY=true; shift ;;
        --upload-only) UPLOAD_ONLY=true; shift ;;
        --rebuild) REBUILD=true; shift ;;
        --help) show_usage; exit 0 ;;
        *) log_error "Unknown option: $1"; show_usage; exit 1 ;;
    esac
done

if [ "$UPLOAD_ONLY" = false ]; then
    pack_project
fi

if [ "$PACK_ONLY" = false ]; then
    if [ "$UPLOAD_ONLY" = true ]; then
        upload_to_server
    else
        upload_to_server
        deploy_on_server $REBUILD
    fi
fi

log_success "All operations completed!"
echo ""
log_info "Access your staging application at:"
log_info "  Admin Panel: https://ark3.qiaoqiaoai.cn/qiao-dash/"
log_info "  API: https://ark3.qiaoqiaoai.cn/api/v1/"
