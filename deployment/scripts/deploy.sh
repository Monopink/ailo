#!/bin/bash
# Deployment Script for Test Environment
# Usage: ./deploy.sh <action> [options]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_DIR="/opt/says-test/says"
DEPLOYMENT_DIR="$PROJECT_DIR/deployment"
COMPOSE_FILE="$DEPLOYMENT_DIR/docker-compose.test.yml"
ENV_FILE="$DEPLOYMENT_DIR/.env.test"
BACKUP_DIR="/opt/says-test/backups"

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

# Check requirements
check_requirements() {
    if [ ! -f "$COMPOSE_FILE" ]; then
        log_error "Docker compose file not found: $COMPOSE_FILE"
        exit 1
    fi

    if [ ! -f "$ENV_FILE" ]; then
        log_error "Environment file not found: $ENV_FILE"
        log_info "Please create $ENV_FILE from .env.test.example"
        exit 1
    fi

    # Required keys validation (fail fast)
    local required_keys=(
        "WECHAT_APP_ID"
        "WECHAT_APP_SECRET"
    )
    local missing=false
    for key in "${required_keys[@]}"; do
        if ! grep -q "^${key}=" "$ENV_FILE"; then
            log_error "Missing required env: ${key} in $ENV_FILE"
            missing=true
        else
            # Ensure not empty value
            local value
            value=$(grep "^${key}=" "$ENV_FILE" | sed -e "s/^${key}=//")
            if [ -z "$value" ]; then
                log_error "Empty value for required env: ${key} in $ENV_FILE"
                missing=true
            fi
        fi
    done
    if [ "$missing" = true ]; then
        log_info "Edit $ENV_FILE to include required values, then retry."
        exit 1
    fi
}

# Backup current code
backup_code() {
    log_info "Backing up current code..."
    local timestamp=$(date +%Y%m%d-%H%M%S)
    local backup_file="$BACKUP_DIR/code/backup-$timestamp.tar.gz"

    mkdir -p "$BACKUP_DIR/code"
    tar -czf "$backup_file" -C "$PROJECT_DIR" . 2>/dev/null || true

    # Keep only last 3 backups
    cd "$BACKUP_DIR/code"
    ls -t backup-*.tar.gz | tail -n +4 | xargs rm -f 2>/dev/null || true

    log_success "Code backed up to $backup_file"
}

# Backup database
backup_database() {
    log_info "Backing up database..."
    local timestamp=$(date +%Y%m%d-%H%M%S)
    local backup_file="$BACKUP_DIR/database/db-$timestamp.sql.gz"

    mkdir -p "$BACKUP_DIR/database"

    docker exec postgres_test_container pg_dump -U says_admin says_test | gzip > "$backup_file"

    # Keep only last 7 days of backups
    find "$BACKUP_DIR/database" -name "db-*.sql.gz" -mtime +7 -delete

    log_success "Database backed up to $backup_file"
}

# Start services
start_services() {
    log_info "Starting services..."
    check_requirements

    cd "$DEPLOYMENT_DIR"
    docker-compose -f docker-compose.test.yml --env-file .env.test up -d

    log_info "Waiting for services to be ready..."
    sleep 30

    check_health
    log_success "Services started successfully"
}

# Stop services
stop_services() {
    log_info "Stopping services..."
    cd "$DEPLOYMENT_DIR"
    docker-compose -f docker-compose.test.yml --env-file .env.test down
    log_success "Services stopped"
}

# Restart services
restart_services() {
    log_info "Restarting services..."
    cd "$DEPLOYMENT_DIR"
    docker-compose -f docker-compose.test.yml --env-file .env.test restart
    log_success "Services restarted"
}

# Deploy new code package
deploy_package() {
    local package_path=$1

    if [ -z "$package_path" ]; then
        log_error "Package path is required"
        log_info "Usage: ./deploy.sh deploy --package <path-to-tar.gz>"
        exit 1
    fi

    if [ ! -f "$package_path" ]; then
        log_error "Package file not found: $package_path"
        exit 1
    fi

    log_info "Deploying package: $package_path"

    # Backup before deployment
    backup_code
    backup_database

    # Stop services
    log_info "Stopping services..."
    cd "$DEPLOYMENT_DIR"
    docker-compose -f docker-compose.test.yml --env-file .env.test down

    # Extract package to temporary directory
    local temp_dir="/tmp/says-deploy-$(date +%Y%m%d%H%M%S)"
    mkdir -p "$temp_dir"
    log_info "Extracting package to $temp_dir..."
    tar -xzf "$package_path" -C "$temp_dir"

    # Check if extraction created says subdirectory
    if [ -d "$temp_dir/says" ]; then
        log_info "Moving files from says subdirectory..."
        mv "$temp_dir/says"/* "$temp_dir/" 2>/dev/null || true
        rmdir "$temp_dir/says" 2>/dev/null || true
    fi

    # Backup current .env.test
    if [ -f "$ENV_FILE" ]; then
        cp "$ENV_FILE" "$ENV_FILE.backup"
        log_info "Backed up .env.test"
    fi

    # Copy new files to project directory
    log_info "Copying new files to $PROJECT_DIR..."
    rsync -av --delete \
        --exclude='.env.test' \
        --exclude='logs' \
        --exclude='__pycache__' \
        "$temp_dir/" "$PROJECT_DIR/"

    # Restore .env.test
    if [ -f "$ENV_FILE.backup" ]; then
        mv "$ENV_FILE.backup" "$ENV_FILE"
        log_info "Restored .env.test"
    fi

    # Check .env.test completeness
    log_info "Checking .env.test configuration..."
    if ! grep -q "REDIS_URL" "$ENV_FILE"; then
        log_warning "REDIS_URL not found in .env.test, adding default value..."
        echo "" >> "$ENV_FILE"
        echo "# Redis Configuration" >> "$ENV_FILE"
        echo "REDIS_URL=redis://localhost:6379/0" >> "$ENV_FILE"
    fi

    # Remove default.conf if exists
    local default_conf="$PROJECT_DIR/nginx/conf.d/default.conf"
    if [ -f "$default_conf" ]; then
        rm -f "$default_conf"
        log_info "Removed default.conf"
    fi

    # Cleanup temp directory
    rm -rf "$temp_dir"

    # Rebuild and start services
    log_info "Rebuilding Docker images..."
    cd "$DEPLOYMENT_DIR"
    docker-compose -f docker-compose.test.yml --env-file .env.test build --no-cache

    log_info "Starting services..."
    docker-compose -f docker-compose.test.yml --env-file .env.test up -d

    log_info "Waiting for services to be ready..."
    sleep 30

    # Initialize migration state
    log_info "Initializing migration state..."
    docker exec backend_test_container alembic stamp 20251106_0000 || log_warning "Failed to stamp baseline"

    # Run migrations
    log_info "Running database migrations..."
    docker exec backend_test_container alembic upgrade head || log_warning "Migration failed or no new migrations"

    # Check health
    check_health

    log_success "Package deployed successfully"
}

# Update services
update_services() {
    local rebuild=${1:-false}
    local migrate=${2:-true}

    log_info "Updating services..."
    check_requirements

    # Backup before update
    backup_code
    backup_database

    cd "$DEPLOYMENT_DIR"

    if [ "$rebuild" = true ]; then
        log_info "Rebuilding Docker images..."
        docker-compose -f docker-compose.test.yml --env-file .env.test build --no-cache
    fi

    # Update services
    docker-compose -f docker-compose.test.yml --env-file .env.test up -d

    # Run migrations if requested
    if [ "$migrate" = true ]; then
        log_info "Running database migrations..."
        sleep 10  # Wait for backend to be ready

        # Check if alembic_version table exists and is empty, if so stamp baseline
        if docker exec postgres_test_container psql -U says_admin -d says_test -tAc "SELECT COUNT(*) FROM alembic_version" 2>/dev/null | grep -q "^0$"; then
            log_info "Stamping baseline migration..."
            docker exec backend_test_container alembic stamp 20251106_0000 || log_warning "Failed to stamp baseline"
        fi

        docker exec backend_test_container alembic upgrade head || log_warning "Migration failed or no new migrations"
    fi

    log_success "Services updated successfully"
}

# Check service health
check_health() {
    log_info "Checking service health..."

    local services=("postgres_test_container" "backend_test_container" "nginx_test_container")
    local all_healthy=true

    for service in "${services[@]}"; do
        if docker ps | grep -q "$service"; then
            log_success "$service is running"
        else
            log_error "$service is not running"
            all_healthy=false
        fi
    done

    # Check backend health endpoint via Nginx container network
    sleep 5
    if docker exec nginx_test_container sh -lc "(command -v curl >/dev/null 2>&1) || (apk add --no-cache curl >/dev/null 2>&1); curl -sf http://backend_test_container:8000/health >/dev/null"; then
        log_success "Backend health check passed"
    else
        log_warning "Backend health check failed (may still be starting)"
    fi

    if [ "$all_healthy" = false ]; then
        log_error "Some services are not healthy"
        return 1
    fi
}

# Show logs
show_logs() {
    local service=${1:-""}
    cd "$DEPLOYMENT_DIR"

    if [ -n "$service" ]; then
        log_info "Showing logs for $service..."
        docker-compose -f docker-compose.test.yml --env-file .env.test logs -f "$service"
    else
        log_info "Showing logs for all services..."
        docker-compose -f docker-compose.test.yml --env-file .env.test logs -f
    fi
}

# Setup SSL
setup_ssl() {
    log_info "Setting up SSL certificate..."
    cd "$DEPLOYMENT_DIR"

    # Check if nginx is running
    if ! docker ps | grep -q "nginx_test_container"; then
        log_error "Nginx is not running. Start services first."
        exit 1
    fi

    # Request certificate
    docker-compose -f docker-compose.test.yml --env-file .env.test run --rm certbot_test

    # Reload nginx
    docker-compose -f docker-compose.test.yml --env-file .env.test restart nginx_test

    log_success "SSL certificate setup completed"
}

# Show status
show_status() {
    log_info "Service Status:"
    cd "$DEPLOYMENT_DIR"
    docker-compose -f docker-compose.test.yml --env-file .env.test ps

    log_info ""
    log_info "Resource Usage:"
    docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}"
}

# Main script logic
ACTION=${1:-help}

case "$ACTION" in
    "start")
        start_services
        ;;
    "stop")
        stop_services
        ;;
    "restart")
        restart_services
        ;;
    "deploy")
        PACKAGE_PATH=""
        shift
        while [[ $# -gt 0 ]]; do
            case $1 in
                --package)
                    PACKAGE_PATH="$2"
                    shift 2
                    ;;
                *)
                    shift
                    ;;
            esac
        done
        deploy_package "$PACKAGE_PATH"
        ;;
    "update")
        REBUILD=false
        MIGRATE=true
        shift
        while [[ $# -gt 0 ]]; do
            case $1 in
                --rebuild)
                    REBUILD=true
                    shift
                    ;;
                --no-migrate)
                    MIGRATE=false
                    shift
                    ;;
                *)
                    shift
                    ;;
            esac
        done
        update_services $REBUILD $MIGRATE
        ;;
    "logs")
        show_logs $2
        ;;
    "status")
        show_status
        ;;
    "health")
        check_health
        ;;
    "ssl")
        setup_ssl
        ;;
    "backup")
        backup_code
        backup_database
        ;;
    "help"|*)
        echo "Usage: $0 <action> [options]"
        echo ""
        echo "Actions:"
        echo "  start          - Start all services"
        echo "  stop           - Stop all services"
        echo "  restart        - Restart all services"
        echo "  deploy         - Deploy new code package"
        echo "  update         - Update services (default: with migration)"
        echo "  logs [service] - Show logs (optionally specify service)"
        echo "  status         - Show service status"
        echo "  health         - Check service health"
        echo "  ssl            - Setup SSL certificate"
        echo "  backup         - Backup code and database"
        echo ""
        echo "Deploy Options:"
        echo "  --package <path> - Path to deployment package (tar.gz)"
        echo ""
        echo "Update Options:"
        echo "  --rebuild      - Rebuild Docker images"
        echo "  --no-migrate   - Skip database migration"
        echo ""
        echo "Examples:"
        echo "  $0 start"
        echo "  $0 deploy --package /home/ubuntu/says-test-deploy-20251017-001234.tar.gz"
        echo "  $0 update"
        echo "  $0 update --rebuild"
        echo "  $0 logs backend_test"
        ;;
esac
