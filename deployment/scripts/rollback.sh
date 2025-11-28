#!/bin/bash
# Rollback Script for Test Environment
# Usage: ./rollback.sh [options]

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

# List available backups
list_backups() {
    log_info "Available code backups:"
    ls -lht "$BACKUP_DIR/code/" | grep "backup-" | head -n 5

    log_info ""
    log_info "Available database backups:"
    ls -lht "$BACKUP_DIR/database/" | grep "db-" | head -n 5
}

# Rollback code
rollback_code() {
    local version=${1:-1}

    log_info "Rolling back code to version $version..."

    # Get the backup file
    local backup_file=$(ls -t "$BACKUP_DIR/code/backup-"*.tar.gz | sed -n "${version}p")

    if [ -z "$backup_file" ]; then
        log_error "Backup version $version not found"
        exit 1
    fi

    log_info "Using backup: $backup_file"

    # Stop services
    log_info "Stopping services..."
    cd "$DEPLOYMENT_DIR"
    docker-compose -f docker-compose.test.yml down

    # Backup current version before rollback
    local timestamp=$(date +%Y%m%d-%H%M%S)
    log_info "Backing up current version..."
    tar -czf "$BACKUP_DIR/code/pre-rollback-$timestamp.tar.gz" -C "$PROJECT_DIR" .

    # Extract backup
    log_info "Extracting backup..."
    rm -rf "$PROJECT_DIR"/*
    tar -xzf "$backup_file" -C "$PROJECT_DIR"

    # Restart services
    log_info "Starting services..."
    cd "$DEPLOYMENT_DIR"
    docker-compose -f docker-compose.test.yml up -d

    log_success "Code rolled back successfully"
}

# Rollback database
rollback_database() {
    local version=${1:-1}

    log_warning "⚠️  WARNING: This will restore the database to a previous state!"
    log_warning "⚠️  All data changes since the backup will be lost!"
    read -p "Are you sure you want to continue? (yes/no): " confirm

    if [ "$confirm" != "yes" ]; then
        log_info "Rollback cancelled"
        exit 0
    fi

    log_info "Rolling back database to version $version..."

    # Get the backup file
    local backup_file=$(ls -t "$BACKUP_DIR/database/db-"*.sql.gz | sed -n "${version}p")

    if [ -z "$backup_file" ]; then
        log_error "Database backup version $version not found"
        exit 1
    fi

    log_info "Using backup: $backup_file"

    # Backup current database before rollback
    local timestamp=$(date +%Y%m%d-%H%M%S)
    log_info "Backing up current database..."
    docker exec postgres_test_container pg_dump -U says_admin says_test | gzip > "$BACKUP_DIR/database/pre-rollback-$timestamp.sql.gz"

    # Restore database
    log_info "Restoring database..."
    gunzip -c "$backup_file" | docker exec -i postgres_test_container psql -U says_admin -d says_test

    # Restart backend
    log_info "Restarting backend..."
    docker restart backend_test_container

    log_success "Database rolled back successfully"
}

# Rollback migration
rollback_migration() {
    local steps=${1:-1}

    log_info "Rolling back $steps database migration(s)..."

    # Show current migration
    log_info "Current migration:"
    docker exec backend_test_container python migrate.py current

    # Rollback
    docker exec backend_test_container python migrate.py downgrade -$steps

    log_success "Migration rolled back successfully"

    # Show new migration
    log_info "New migration:"
    docker exec backend_test_container python migrate.py current
}

# Main script logic
ROLLBACK_CODE=false
ROLLBACK_DATABASE=false
ROLLBACK_MIGRATION=false
VERSION=1

while [[ $# -gt 0 ]]; do
    case $1 in
        --code)
            ROLLBACK_CODE=true
            shift
            ;;
        --database)
            ROLLBACK_DATABASE=true
            shift
            ;;
        --migration)
            ROLLBACK_MIGRATION=true
            shift
            if [[ $1 =~ ^[0-9]+$ ]]; then
                VERSION=$1
                shift
            fi
            ;;
        --all)
            ROLLBACK_CODE=true
            ROLLBACK_DATABASE=true
            shift
            ;;
        --version)
            VERSION=$2
            shift 2
            ;;
        --list)
            list_backups
            exit 0
            ;;
        --help)
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  --code              Rollback code to previous version"
            echo "  --database          Rollback database to previous backup"
            echo "  --migration [N]     Rollback N database migrations (default: 1)"
            echo "  --all               Rollback both code and database"
            echo "  --version N         Rollback to version N (default: 1 = last backup)"
            echo "  --list              List available backups"
            echo "  --help              Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0 --code                    # Rollback code to last backup"
            echo "  $0 --database                # Rollback database to last backup"
            echo "  $0 --migration 2             # Rollback 2 migrations"
            echo "  $0 --all                     # Rollback both code and database"
            echo "  $0 --code --version 2        # Rollback code to 2nd last backup"
            echo "  $0 --list                    # List available backups"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Default: rollback code if no option specified
if [ "$ROLLBACK_CODE" = false ] && [ "$ROLLBACK_DATABASE" = false ] && [ "$ROLLBACK_MIGRATION" = false ]; then
    ROLLBACK_CODE=true
fi

# Execute rollback
if [ "$ROLLBACK_MIGRATION" = true ]; then
    rollback_migration $VERSION
fi

if [ "$ROLLBACK_CODE" = true ]; then
    rollback_code $VERSION
fi

if [ "$ROLLBACK_DATABASE" = true ]; then
    rollback_database $VERSION
fi

log_success "Rollback completed successfully"
