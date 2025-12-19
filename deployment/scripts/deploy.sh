#!/bin/bash
# Deployment Script for Staging Environment
# Usage: ./deploy.sh <action> [options]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
DEPLOYMENT_DIR="$PROJECT_DIR/deployment"
COMPOSE_FILE="$DEPLOYMENT_DIR/docker-compose.staging.yml"
ENV_FILE="$DEPLOYMENT_DIR/.env.staging"
BACKUP_DIR="/opt/ailo-staging/backups"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Logging functions
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Get container name by service
get_container() {
    docker-compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps --format "{{.Name}}" "$1" 2>/dev/null | head -1
}

# Check requirements
check_requirements() {
    if [ ! -f "$COMPOSE_FILE" ]; then
        log_error "Docker compose file not found: $COMPOSE_FILE"
        exit 1
    fi
    if [ ! -f "$ENV_FILE" ]; then
        log_error "Environment file not found: $ENV_FILE"
        exit 1
    fi
}

# Backup code
backup_code() {
    log_info "Backing up code..."
    local timestamp=$(date +%Y%m%d-%H%M%S)
    local backup_file="$BACKUP_DIR/code/backup-$timestamp.tar.gz"

    mkdir -p "$BACKUP_DIR/code"
    tar -czf "$backup_file" -C "$PROJECT_DIR" \
        --exclude='*.pyc' --exclude='__pycache__' --exclude='*.log' --exclude='logs/*' \
        . 2>/dev/null || true

    # Keep only last 3 backups
    cd "$BACKUP_DIR/code" && ls -t backup-*.tar.gz | tail -n +4 | xargs rm -f 2>/dev/null || true
    log_success "Code backed up to $backup_file"
}

# Backup database
backup_database() {
    log_info "Backing up database..."
    local timestamp=$(date +%Y%m%d-%H%M%S)
    local backup_file="$BACKUP_DIR/database/db-$timestamp.sql.gz"
    local postgres_container=$(get_container "postgres")

    if [ -z "$postgres_container" ]; then
        log_error "PostgreSQL container not found"
        return 1
    fi

    mkdir -p "$BACKUP_DIR/database"
    docker exec "$postgres_container" pg_dump -U ailo_user ailo | gzip > "$backup_file"

    # Keep only last 7 days
    find "$BACKUP_DIR/database" -name "db-*.sql.gz" -mtime +7 -delete 2>/dev/null || true
    log_success "Database backed up to $backup_file"
}

# Start services
start_services() {
    log_info "Starting services..."
    check_requirements
    cd "$DEPLOYMENT_DIR"
    docker-compose -f docker-compose.staging.yml --env-file .env.staging up -d
    log_info "Waiting for services..."
    sleep 30
    check_health
    log_success "Services started successfully"
}

# Stop services
stop_services() {
    log_info "Stopping services..."
    cd "$DEPLOYMENT_DIR"
    docker-compose -f docker-compose.staging.yml --env-file .env.staging down
    log_success "Services stopped"
}

# Restart services
restart_services() {
    log_info "Restarting services..."
    cd "$DEPLOYMENT_DIR"
    docker-compose -f docker-compose.staging.yml --env-file .env.staging restart
    log_success "Services restarted"
}

# Update services
update_services() {
    local rebuild=${1:-false}

    log_info "Updating services..."
    check_requirements
    backup_code
    backup_database

    cd "$DEPLOYMENT_DIR"

    if [ "$rebuild" = true ]; then
        log_info "Rebuilding Docker images..."
        docker-compose -f docker-compose.staging.yml --env-file .env.staging build --no-cache
    fi

    docker-compose -f docker-compose.staging.yml --env-file .env.staging up -d

    log_info "Running database migrations..."
    sleep 10
    local backend_container=$(get_container "backend")
    if [ -n "$backend_container" ]; then
        docker exec "$backend_container" alembic upgrade head || log_warning "Migration failed or no new migrations"
    fi

    log_success "Services updated successfully"
}

# Check health
check_health() {
    log_info "Checking service health..."
    local failed=0

    for service in postgres backend nginx; do
        local container=$(get_container "$service")
        if [ -n "$container" ] && docker ps | grep -q "$container"; then
            log_success "$service is running"
        else
            log_error "$service is not running"
            failed=$((failed + 1))
        fi
    done

    if [ $failed -eq 0 ]; then
        log_success "All services healthy"
    else
        log_error "$failed service(s) failed"
        return 1
    fi
}

# Show logs
show_logs() {
    local service=${1:-""}
    cd "$DEPLOYMENT_DIR"

    if [ -n "$service" ]; then
        docker-compose -f docker-compose.staging.yml --env-file .env.staging logs -f "$service"
    else
        docker-compose -f docker-compose.staging.yml --env-file .env.staging logs -f
    fi
}

# Show status
show_status() {
    log_info "Service Status:"
    cd "$DEPLOYMENT_DIR"
    docker-compose -f docker-compose.staging.yml --env-file .env.staging ps

    echo ""
    log_info "Resource Usage:"
    docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}"
}

# Main logic
ACTION=${1:-help}

case "$ACTION" in
    start)
        start_services
        ;;
    stop)
        stop_services
        ;;
    restart)
        restart_services
        ;;
    update)
        REBUILD=false
        shift
        while [[ $# -gt 0 ]]; do
            case $1 in
                --rebuild) REBUILD=true; shift ;;
                *) shift ;;
            esac
        done
        update_services $REBUILD
        ;;
    logs)
        show_logs $2
        ;;
    status)
        show_status
        ;;
    health)
        check_health
        ;;
    backup)
        backup_code
        backup_database
        ;;
    help|*)
        echo "Usage: $0 <action> [options]"
        echo ""
        echo "Actions:"
        echo "  start          - Start all services"
        echo "  stop           - Stop all services"
        echo "  restart        - Restart all services"
        echo "  update         - Update services (with auto backup)"
        echo "  logs [service] - Show logs"
        echo "  status         - Show service status"
        echo "  health         - Check service health"
        echo "  backup         - Backup code and database"
        echo ""
        echo "Update Options:"
        echo "  --rebuild      - Rebuild Docker images"
        echo ""
        echo "Examples:"
        echo "  $0 start"
        echo "  $0 update"
        echo "  $0 update --rebuild"
        echo "  $0 logs backend"
        ;;
esac
