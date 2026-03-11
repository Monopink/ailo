#!/usr/bin/env bash

# Deployment Script for Production Environment
# Usage: ./deploy.sh <action> [options]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"
DEPLOYMENT_DIR="$PROJECT_DIR/deployment/prod"
COMPOSE_FILES=(
    "$PROJECT_DIR/deployment/compose.base.yaml"
    "$DEPLOYMENT_DIR/compose.yaml"
)
ENV_FILE="$DEPLOYMENT_DIR/.env"
BACKUP_DIR="/opt/ailo-prod/backups"
BASIC_AUTH_FILE="$DEPLOYMENT_DIR/secrets/.htpasswd"
DEPLOYMENT_SCRIPTS_DIR="$PROJECT_DIR/deployment/scripts"
EXPECTED_ENVIRONMENT="production"
NGINX_LOG_DIR="/opt/ailo-prod/logs/nginx"

. "$DEPLOYMENT_SCRIPTS_DIR/deploy-lib.sh"

validate_env_values() {
    local required_keys=(
        "DOMAIN"
        "POSTGRES_PASSWORD"
        "DB_PASSWORD"
        "JWT_SECRET_KEY"
        "ADMIN_SECRET_KEY"
        "ADMIN_TURNSTILE_SECRET_KEY"
        "ADMIN_TURNSTILE_SITE_KEY"
        "LEANCLOUD_MASTER_KEY"
        "LEANCLOUD_IM_APP_ID"
        "LEANCLOUD_IM_APP_KEY"
        "DOUBAO_API_KEY"
        "WECHAT_APP_ID"
        "WECHAT_APP_SECRET"
        "TENCENT_COS_MEDIA_SECRET_ID"
        "TENCENT_COS_MEDIA_SECRET_KEY"
        "TENCENT_COS_MEDIA_REGION"
        "TENCENT_COS_MEDIA_BUCKET"
        "TENCENT_COS_MEDIA_ENDPOINT"
        "TENCENT_COS_BACKUP_SECRET_ID"
        "TENCENT_COS_BACKUP_SECRET_KEY"
        "TENCENT_COS_BACKUP_REGION"
        "TENCENT_COS_BACKUP_BUCKET"
        "TENCENT_COS_BACKUP_ENDPOINT"
        "CORS_ORIGINS"
        "ALLOWED_HOSTS"
    )
    local invalid_keys=()

    for key in "${required_keys[@]}"; do
        local value
        value=$(get_env_value "$key")
        if [ -z "$value" ]; then
            invalid_keys+=("${key}(missing)")
            continue
        fi

        if [[ "$value" == *"CHANGE_IN_PRODUCTION"* ]] || [[ "$value" == *"example.com"* ]]; then
            invalid_keys+=("$key")
        fi
    done

    if [ "${#invalid_keys[@]}" -gt 0 ]; then
        log_error "Environment contains unresolved placeholder/default values:"
        for key in "${invalid_keys[@]}"; do
            log_error "  - $key"
        done
        log_error "Please update $BASE_ENV_FILE and/or $ENV_FILE before deployment."
        exit 1
    fi
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

    local prod_root="/opt/ailo-prod"
    local target_project="$prod_root/ailo"
    local timestamp
    timestamp=$(date +%Y%m%d-%H%M%S)
    local temp_dir
    temp_dir=$(mktemp -d "/tmp/ailo-deploy-${timestamp}-XXXXXX")
    local extracted_project="$temp_dir/ailo"
    local previous_project="$prod_root/ailo.predeploy.${timestamp}"
    local base_env_backup="$temp_dir/.env.base.backup"
    local env_backup="$temp_dir/.env.backup"
    local auth_backup="$temp_dir/.htpasswd.backup"
    local deploy_owner="$(id -un)"
    local deploy_group="$(id -gn)"

    log_info "Deploying package: $package"
    tar -xzf "$package" -C "$temp_dir"

    if [ ! -d "$extracted_project" ]; then
        rm -rf "$temp_dir"
        log_error "Invalid package structure, missing top-level directory: ailo/"
        exit 1
    fi

    # Preserve current env files because deployment packages do not include .env files.
    if [ -f "$target_project/deployment/.env" ]; then
        cp "$target_project/deployment/.env" "$base_env_backup"
    fi
    if [ -f "$base_env_backup" ]; then
        mkdir -p "$extracted_project/deployment"
        cp "$base_env_backup" "$extracted_project/deployment/.env"
    fi

    if [ -f "$target_project/deployment/prod/.env" ]; then
        cp "$target_project/deployment/prod/.env" "$env_backup"
    fi
    if [ -f "$env_backup" ]; then
        mkdir -p "$extracted_project/deployment/prod"
        cp "$env_backup" "$extracted_project/deployment/prod/.env"
    fi

    if [ -f "$target_project/deployment/prod/secrets/.htpasswd" ]; then
        cp "$target_project/deployment/prod/secrets/.htpasswd" "$auth_backup"
    fi
    if [ -f "$auth_backup" ]; then
        mkdir -p "$extracted_project/deployment/prod/secrets"
        cp "$auth_backup" "$extracted_project/deployment/prod/secrets/.htpasswd"
    fi

    if [ -d "$target_project" ]; then
        deploy_owner=$(stat -c '%U' "$target_project")
        deploy_group=$(stat -c '%G' "$target_project")

        backup_code
        if ! backup_database; then
            log_warning "Database backup skipped because database container is unavailable"
        fi

        log_info "Stopping current services..."
        bash "$target_project/deployment/prod/scripts/deploy.sh" stop || log_warning "Failed to stop services cleanly"

        mv "$target_project" "$previous_project"
    else
        mkdir -p "$prod_root"
    fi

    mv "$extracted_project" "$target_project"

    chown -R "$deploy_owner:$deploy_group" "$target_project"
    find "$target_project" -type d -exec chmod 755 {} +
    find "$target_project" -type f -exec chmod 644 {} +

    chmod +x "$target_project/deployment/prod/scripts/"*.sh 2>/dev/null || true
    chmod +x "$target_project/deployment/scripts/"*.sh 2>/dev/null || true
    chmod +x "$target_project/deployment/fail2ban/"*.sh 2>/dev/null || true

    if [ -f "$target_project/deployment/prod/.env" ]; then
        chmod 600 "$target_project/deployment/prod/.env"
    fi
    if [ -f "$target_project/deployment/prod/secrets/.htpasswd" ]; then
        chmod 600 "$target_project/deployment/prod/secrets/.htpasswd"
    fi

    mkdir -p "$target_project/logs"
    chown -R "$deploy_owner:$deploy_group" "$target_project/logs"
    chmod 775 "$target_project/logs"

    rm -rf "$temp_dir"

    log_info "Starting updated services..."
    if [ "$rebuild" = true ]; then
        bash "$target_project/deployment/prod/scripts/deploy.sh" update --rebuild --skip-backup
    else
        bash "$target_project/deployment/prod/scripts/deploy.sh" update --skip-backup
    fi
    log_success "Package deployment completed"

    if [ -d "$previous_project" ]; then
        log_info "Previous code backup: $previous_project"
    fi
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
        echo "  $0 deploy --package /home/ubuntu/ailo-prod-deploy-YYYYMMDD-HHMMSS.tar.gz"
        echo "  $0 update"
        echo "  $0 update --rebuild"
        echo "  $0 logs backend"
        ;;
esac
