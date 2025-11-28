#!/bin/bash
# Backup Script for Test Environment
# Usage: ./backup.sh [type]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_DIR="/opt/says-test/says"
BACKUP_DIR="/opt/says-test/backups"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)

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

# Backup code
backup_code() {
    log_info "Backing up code..."

    local backup_file="$BACKUP_DIR/code/backup-$TIMESTAMP.tar.gz"
    mkdir -p "$BACKUP_DIR/code"

    # Create backup
    tar -czf "$backup_file" -C "$PROJECT_DIR" \
        --exclude='*.pyc' \
        --exclude='__pycache__' \
        --exclude='*.log' \
        --exclude='logs/*' \
        . 2>/dev/null || true

    local size=$(du -h "$backup_file" | cut -f1)
    log_success "Code backed up to $backup_file ($size)"

    # Keep only last 3 backups
    cd "$BACKUP_DIR/code"
    ls -t backup-*.tar.gz | tail -n +4 | xargs rm -f 2>/dev/null || true

    log_info "Kept last 3 code backups"
}

# Backup database
backup_database() {
    log_info "Backing up database..."

    local backup_file="$BACKUP_DIR/database/db-$TIMESTAMP.sql.gz"
    mkdir -p "$BACKUP_DIR/database"

    # Check if database container is running
    if ! docker ps | grep -q "postgres_test_container"; then
        log_error "Database container is not running"
        return 1
    fi

    # Create backup
    docker exec postgres_test_container pg_dump -U says_admin says_test | gzip > "$backup_file"

    local size=$(du -h "$backup_file" | cut -f1)
    log_success "Database backed up to $backup_file ($size)"

    # Keep only last 7 days of backups
    find "$BACKUP_DIR/database" -name "db-*.sql.gz" -mtime +7 -delete

    log_info "Kept last 7 days of database backups"
}

# Show backup statistics
show_stats() {
    log_info "Backup Statistics:"

    if [ -d "$BACKUP_DIR/code" ]; then
        local code_count=$(ls -1 "$BACKUP_DIR/code/backup-"*.tar.gz 2>/dev/null | wc -l)
        local code_size=$(du -sh "$BACKUP_DIR/code" 2>/dev/null | cut -f1)
        echo "  Code backups: $code_count files ($code_size)"
    fi

    if [ -d "$BACKUP_DIR/database" ]; then
        local db_count=$(ls -1 "$BACKUP_DIR/database/db-"*.sql.gz 2>/dev/null | wc -l)
        local db_size=$(du -sh "$BACKUP_DIR/database" 2>/dev/null | cut -f1)
        echo "  Database backups: $db_count files ($db_size)"
    fi

    log_info ""
    log_info "Recent code backups:"
    ls -lht "$BACKUP_DIR/code/" 2>/dev/null | grep "backup-" | head -n 3 || echo "  No backups found"

    log_info ""
    log_info "Recent database backups:"
    ls -lht "$BACKUP_DIR/database/" 2>/dev/null | grep "db-" | head -n 3 || echo "  No backups found"
}

# Clean old backups
clean_old_backups() {
    log_info "Cleaning old backups..."

    # Keep only last 3 code backups
    if [ -d "$BACKUP_DIR/code" ]; then
        cd "$BACKUP_DIR/code"
        local removed=$(ls -t backup-*.tar.gz 2>/dev/null | tail -n +4 | wc -l)
        ls -t backup-*.tar.gz 2>/dev/null | tail -n +4 | xargs rm -f 2>/dev/null || true
        log_info "Removed $removed old code backup(s)"
    fi

    # Keep only last 7 days of database backups
    if [ -d "$BACKUP_DIR/database" ]; then
        local removed=$(find "$BACKUP_DIR/database" -name "db-*.sql.gz" -mtime +7 2>/dev/null | wc -l)
        find "$BACKUP_DIR/database" -name "db-*.sql.gz" -mtime +7 -delete 2>/dev/null || true
        log_info "Removed $removed old database backup(s)"
    fi

    log_success "Cleanup completed"
}

# Main script logic
TYPE=${1:-all}

case "$TYPE" in
    "code")
        backup_code
        ;;
    "database")
        backup_database
        ;;
    "all")
        backup_code
        backup_database
        ;;
    "stats")
        show_stats
        ;;
    "clean")
        clean_old_backups
        ;;
    "help"|*)
        echo "Usage: $0 [type]"
        echo ""
        echo "Types:"
        echo "  code       - Backup code only"
        echo "  database   - Backup database only"
        echo "  all        - Backup both code and database (default)"
        echo "  stats      - Show backup statistics"
        echo "  clean      - Clean old backups"
        echo ""
        echo "Examples:"
        echo "  $0              # Backup everything"
        echo "  $0 code         # Backup code only"
        echo "  $0 database     # Backup database only"
        echo "  $0 stats        # Show backup statistics"
        echo "  $0 clean        # Clean old backups"
        ;;
esac
