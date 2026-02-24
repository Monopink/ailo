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
    local postgres_container=$(get_container "postgres_staging")

    if [ -z "$postgres_container" ]; then
        log_error "PostgreSQL container not found"
        return 1
    fi

    mkdir -p "$BACKUP_DIR/database"
    local db_user=$(docker exec "$postgres_container" printenv POSTGRES_USER 2>/dev/null || echo "postgres")
    local db_name=$(docker exec "$postgres_container" printenv POSTGRES_DB 2>/dev/null || echo "postgres")
    docker exec "$postgres_container" pg_dump -U "$db_user" "$db_name" | gzip > "$backup_file"

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
    local skip_backup=${2:-false}

    log_info "Updating services..."
    check_requirements
    if [ "$skip_backup" != true ]; then
        backup_code
        backup_database
    fi

    cd "$DEPLOYMENT_DIR"

    if [ "$rebuild" = true ]; then
        log_info "Rebuilding Docker images..."
        docker-compose -f docker-compose.staging.yml --env-file .env.staging build --no-cache
    fi

    docker-compose -f docker-compose.staging.yml --env-file .env.staging up -d

    log_info "Running database migrations..."
    sleep 10
    local backend_container=$(get_container "backend_staging")
    if [ -n "$backend_container" ]; then
        docker exec "$backend_container" alembic upgrade head || log_warning "Migration failed or no new migrations"
    fi

    log_success "Services updated successfully"
}

# Deploy package and then run update
deploy_package() {
    local package=""
    local rebuild=true
    shift

    while [[ $# -gt 0 ]]; do
        case $1 in
            --package)
                if [ -z "${2:-}" ]; then
                    log_error "--package requires a file path"
                    exit 1
                fi
                package="$2"
                shift 2
                ;;
            --rebuild)
                rebuild=true
                shift
                ;;
            --no-rebuild)
                rebuild=false
                shift
                ;;
            *)
                log_warning "Unknown deploy option: $1"
                shift
                ;;
        esac
    done

    if [ -z "$package" ]; then
        log_error "Missing --package argument"
        exit 1
    fi

    if [ ! -f "$package" ]; then
        log_error "Package not found: $package"
        exit 1
    fi

    local staging_root="/opt/ailo-staging"
    local target_project="$staging_root/ailo"
    local timestamp=$(date +%Y%m%d-%H%M%S)
    local temp_dir
    temp_dir=$(mktemp -d "/tmp/ailo-deploy-${timestamp}-XXXXXX")
    local extracted_project="$temp_dir/ailo"
    local previous_project="$staging_root/ailo.predeploy.${timestamp}"
    local env_backup="$temp_dir/.env.staging.backup"

    log_info "Deploying package: $package"
    tar -xzf "$package" -C "$temp_dir"

    if [ ! -d "$extracted_project" ]; then
        rm -rf "$temp_dir"
        log_error "Invalid package structure, missing top-level directory: ailo/"
        exit 1
    fi

    # Preserve current staging env file because deployment packages do not include .env files.
    if [ -f "$target_project/deployment/.env.staging" ]; then
        cp "$target_project/deployment/.env.staging" "$env_backup"
    fi
    if [ -f "$env_backup" ]; then
        mkdir -p "$extracted_project/deployment"
        cp "$env_backup" "$extracted_project/deployment/.env.staging"
    fi

    if [ -d "$target_project" ]; then
        backup_code
        if ! backup_database; then
            log_warning "Database backup skipped because database container is unavailable"
        fi

        if [ -f "$target_project/deployment/docker-compose.staging.yml" ] && [ -f "$target_project/deployment/.env.staging" ]; then
            log_info "Stopping current services..."
            (
                cd "$target_project/deployment" && \
                docker-compose -f docker-compose.staging.yml --env-file .env.staging down
            ) || log_warning "Failed to stop services cleanly"
        fi

        mv "$target_project" "$previous_project"
    else
        mkdir -p "$staging_root"
    fi

    mv "$extracted_project" "$target_project"
    chmod +x "$target_project/deployment/scripts/"*.sh 2>/dev/null || true
    rm -rf "$temp_dir"

    log_info "Starting updated services..."
    if [ "$rebuild" = true ]; then
        bash "$target_project/deployment/scripts/deploy.sh" update --rebuild --skip-backup
    else
        bash "$target_project/deployment/scripts/deploy.sh" update --skip-backup
    fi
    log_success "Package deployment completed"

    if [ -d "$previous_project" ]; then
        log_info "Previous code backup: $previous_project"
    fi
}

# Check health
check_health() {
    log_info "Checking service health..."
    local failed=0

    for service in postgres_staging backend_staging nginx_staging; do
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
        SKIP_BACKUP=false
        shift
        while [[ $# -gt 0 ]]; do
            case $1 in
                --rebuild) REBUILD=true; shift ;;
                --skip-backup) SKIP_BACKUP=true; shift ;;
                *) shift ;;
            esac
        done
        update_services $REBUILD $SKIP_BACKUP
        ;;
    deploy)
        deploy_package "$@"
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
        echo "  deploy         - Deploy package and update services"
        echo "  update         - Update services (with auto backup)"
        echo "  logs [service] - Show logs"
        echo "  status         - Show service status"
        echo "  health         - Check service health"
        echo "  backup         - Backup code and database"
        echo ""
        echo "Deploy Options:"
        echo "  --package PATH - Path to deployment package (.tar.gz)"
        echo "  --rebuild      - Rebuild Docker images (default for deploy)"
        echo "  --no-rebuild   - Skip Docker image rebuild for deploy"
        echo ""
        echo "Update Options:"
        echo "  --rebuild      - Rebuild Docker images"
        echo ""
        echo "Examples:"
        echo "  $0 start"
        echo "  $0 deploy --package /home/ubuntu/ailo-staging-deploy-YYYYMMDD-HHMMSS.tar.gz"
        echo "  $0 update"
        echo "  $0 update --rebuild"
        echo "  $0 logs backend_staging"
        ;;
esac
