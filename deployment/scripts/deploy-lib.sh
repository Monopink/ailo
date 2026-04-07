# Shared deployment helpers for staging/prod scripts.

set -e

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

compose_cmd() {
    if [ -z "${COMPOSE_BAKE+x}" ]; then
        export COMPOSE_BAKE=false
    fi

    if docker compose version >/dev/null 2>&1; then
        docker compose "$@"
        return 0
    fi

    log_error "Docker Compose v2 is not available (missing: 'docker compose')."
    log_error "Install docker-compose-plugin and retry."
    exit 1
}

BASE_ENV_FILE=${BASE_ENV_FILE:-"$PROJECT_DIR/deployment/.env"}
EFFECTIVE_ENV_FILE=""

prepare_effective_env_file() {
    if [ -n "$EFFECTIVE_ENV_FILE" ]; then
        return 0
    fi

    if [ ! -f "$BASE_ENV_FILE" ]; then
        log_error "Baseline environment file not found: $BASE_ENV_FILE"
        log_error "Create it from: $PROJECT_DIR/deployment/.env.example"
        exit 1
    fi
    if [ ! -f "$ENV_FILE" ]; then
        log_error "Environment override file not found: $ENV_FILE"
        log_error "Create it from: $DEPLOYMENT_DIR/.env.example"
        exit 1
    fi

    local tmp
    tmp=$(mktemp "/tmp/ailo-effective-env-${EXPECTED_ENVIRONMENT:-env}-XXXXXX.env")
    chmod 600 "$tmp" 2>/dev/null || true

    # Merge base + override into a single dotenv file for docker compose interpolation.
    # Override values win.
    awk '
        function trim(s) { sub(/^[ \t\r\n]+/, "", s); sub(/[ \t\r\n]+$/, "", s); return s }
        /^[ \t]*($|#)/ { next }
        {
            line=$0
            pos=index(line, "=")
            if (pos <= 1) next
            key=trim(substr(line, 1, pos-1))
            val=substr(line, pos+1)
            if (key == "") next
            v[key]=val
            if (!(key in seen)) { order[++n]=key; seen[key]=1 }
        }
        END {
            for (i=1; i<=n; i++) {
                k=order[i]
                if (k in v) print k "=" v[k]
            }
        }
    ' "$BASE_ENV_FILE" "$ENV_FILE" > "$tmp"

    EFFECTIVE_ENV_FILE="$tmp"
    trap 'rm -f "$EFFECTIVE_ENV_FILE" 2>/dev/null || true' EXIT
}

get_env_value() {
    local key="${1:-}"
    if [ -z "$key" ]; then
        echo ""
        return 0
    fi

    prepare_effective_env_file
    grep -E "^${key}=" "$EFFECTIVE_ENV_FILE" | head -1 | cut -d'=' -f2- || true
}

compose() {
    prepare_effective_env_file
    local compose_args=()

    if declare -p COMPOSE_FILES >/dev/null 2>&1; then
        local compose_file
        for compose_file in "${COMPOSE_FILES[@]}"; do
            compose_args+=(-f "$compose_file")
        done
    elif [ -n "${COMPOSE_FILE:-}" ]; then
        compose_args+=(-f "$COMPOSE_FILE")
    else
        log_error "Docker compose file(s) not configured (COMPOSE_FILES or COMPOSE_FILE)"
        exit 1
    fi

    compose_cmd "${compose_args[@]}" --project-directory "$PROJECT_DIR/deployment" --env-file "$EFFECTIVE_ENV_FILE" "$@"
}

# Get container name by service
get_container() {
    compose ps --format "{{.Name}}" "$1" 2>/dev/null | head -1
}

check_requirements() {
    if declare -p COMPOSE_FILES >/dev/null 2>&1; then
        local compose_file
        for compose_file in "${COMPOSE_FILES[@]}"; do
            if [ ! -f "$compose_file" ]; then
                log_error "Docker compose file not found: $compose_file"
                exit 1
            fi
        done
    elif [ -n "${COMPOSE_FILE:-}" ]; then
        if [ ! -f "$COMPOSE_FILE" ]; then
            log_error "Docker compose file not found: $COMPOSE_FILE"
            exit 1
        fi
    else
        log_error "Docker compose file(s) not configured (COMPOSE_FILES or COMPOSE_FILE)"
        exit 1
    fi

    prepare_effective_env_file
    if [ ! -f "$BASIC_AUTH_FILE" ]; then
        log_error "Basic auth file not found: $BASIC_AUTH_FILE"
        log_error "Run: bash $DEPLOYMENT_SCRIPTS_DIR/generate-basic-auth.sh $EXPECTED_ENVIRONMENT admin"
        exit 1
    fi

    # Nginx inside container must be able to read the file.
    # If the file is too restrictive (e.g. 600), nginx will fail with "Permission denied".
    chmod 644 "$BASIC_AUTH_FILE" 2>/dev/null || true

    if [ -n "$EXPECTED_ENVIRONMENT" ]; then
        local current_env
        current_env=$(get_env_value "ENVIRONMENT" | tr -d '" ')
        if [ "$current_env" != "$EXPECTED_ENVIRONMENT" ]; then
            log_error "ENVIRONMENT must be $EXPECTED_ENVIRONMENT in $ENV_FILE, got: ${current_env:-<empty>}"
            exit 1
        fi
    fi

    if declare -F validate_env_values >/dev/null 2>&1; then
        validate_env_values
    fi

    if [ -n "$NGINX_LOG_DIR" ]; then
        mkdir -p "$NGINX_LOG_DIR"
        touch "$NGINX_LOG_DIR/admin_access.log"
    fi
}

# Backup code
backup_code() {
    log_info "Backing up code..."
    local timestamp
    timestamp=$(date +%Y%m%d-%H%M%S)
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
    local timestamp
    timestamp=$(date +%Y%m%d-%H%M%S)
    local backup_file="$BACKUP_DIR/database/db-$timestamp.sql.gz"
    local postgres_container
    postgres_container=$(get_container "postgres")

    if [ -z "$postgres_container" ]; then
        log_error "PostgreSQL container not found"
        return 1
    fi

    mkdir -p "$BACKUP_DIR/database"
    local db_user
    db_user=$(docker exec "$postgres_container" printenv POSTGRES_USER 2>/dev/null || echo "postgres")
    local db_name
    db_name=$(docker exec "$postgres_container" printenv POSTGRES_DB 2>/dev/null || echo "postgres")
    docker exec "$postgres_container" pg_dump -U "$db_user" "$db_name" | gzip > "$backup_file"

    # Keep only last 7 days
    find "$BACKUP_DIR/database" -name "db-*.sql.gz" -mtime +7 -delete 2>/dev/null || true
    log_success "Database backed up to $backup_file"
}

# Start services
start_services() {
    log_info "Starting services..."
    check_requirements
    compose up -d
    log_info "Waiting for services..."
    sleep 30
    check_health
    log_success "Services started successfully"
}

# Stop services
stop_services() {
    log_info "Stopping services..."
    compose down
    log_success "Services stopped"
}

# Restart services
restart_services() {
    log_info "Restarting services..."
    compose restart
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

    if [ "$rebuild" = true ]; then
        log_info "Rebuilding Docker images..."
        compose build --no-cache
    fi

    compose up -d

    log_info "Running database migrations..."
    sleep 10
    local backend_container
    backend_container=$(get_container "backend")
    if [ -n "$backend_container" ]; then
        if ! docker exec "$backend_container" alembic upgrade head; then
            log_error "Database migration failed"
            return 1
        fi
    else
        log_error "Backend container not found for migration"
        return 1
    fi

    log_success "Services updated successfully"
}

# Check health
check_health() {
    log_info "Checking service health..."
    local failed=0

    for service in postgres backend nginx; do
        local container
        container=$(get_container "$service")
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

    if [ -n "$service" ]; then
        compose logs -f "$service"
    else
        compose logs -f
    fi
}

# Show status
show_status() {
    log_info "Service Status:"
    compose ps

    echo ""
    log_info "Resource Usage:"
    docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}"
}
