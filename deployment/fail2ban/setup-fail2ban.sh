#!/bin/bash
# Install and configure fail2ban for nginx admin basic-auth protection.
# Usage: sudo ./setup-fail2ban.sh <staging|prod> [ignoreip]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
FAIL2BAN_DIR="$PROJECT_DIR/deployment/fail2ban"

TARGET_ENV="${1:-}"
IGNORE_IPS="${2:-127.0.0.1/8 ::1}"

if [[ "$EUID" -ne 0 ]]; then
    echo "[ERROR] Please run as root (use sudo)."
    exit 1
fi

if [[ -z "$TARGET_ENV" || ( "$TARGET_ENV" != "staging" && "$TARGET_ENV" != "prod" ) ]]; then
    echo "Usage: sudo $0 <staging|prod> [ignoreip]"
    exit 1
fi

if [[ "$TARGET_ENV" == "staging" ]]; then
    JAIL_SOURCE="$FAIL2BAN_DIR/jail.d/ailo-nginx-admin-auth-staging.local"
    JAIL_NAME="ailo-nginx-admin-auth-staging"
    NGINX_LOG_PATH="/opt/ailo-staging/logs/nginx/admin_access.log"
else
    JAIL_SOURCE="$FAIL2BAN_DIR/jail.d/ailo-nginx-admin-auth-prod.local"
    JAIL_NAME="ailo-nginx-admin-auth-prod"
    NGINX_LOG_PATH="/opt/ailo-prod/logs/nginx/admin_access.log"
fi

if ! command -v fail2ban-client >/dev/null 2>&1; then
    echo "[INFO] Installing fail2ban..."
    if command -v apt-get >/dev/null 2>&1; then
        apt-get update
        apt-get install -y fail2ban
    elif command -v dnf >/dev/null 2>&1; then
        dnf install -y fail2ban
    elif command -v yum >/dev/null 2>&1; then
        yum install -y fail2ban
    else
        echo "[ERROR] Supported package manager not found (apt-get/dnf/yum)."
        exit 1
    fi
else
    echo "[INFO] fail2ban already installed."
fi

mkdir -p "$(dirname "$NGINX_LOG_PATH")"
touch "$NGINX_LOG_PATH"

install -m 0644 "$FAIL2BAN_DIR/filter.d/ailo-nginx-admin-auth.conf" \
    /etc/fail2ban/filter.d/ailo-nginx-admin-auth.conf
install -m 0644 "$JAIL_SOURCE" /etc/fail2ban/jail.d/ailo-nginx-admin-auth.local
install -m 0644 "$FAIL2BAN_DIR/jail.d/ailo-recidive.local" /etc/fail2ban/jail.d/ailo-recidive.local

sed -i "s|__IGNOREIP__|$IGNORE_IPS|g" /etc/fail2ban/jail.d/ailo-nginx-admin-auth.local
sed -i "s|__IGNOREIP__|$IGNORE_IPS|g" /etc/fail2ban/jail.d/ailo-recidive.local

systemctl enable fail2ban >/dev/null
systemctl restart fail2ban

echo "[INFO] Reloading fail2ban configuration..."
fail2ban-client reload >/dev/null

echo "[INFO] Active jail status:"
fail2ban-client status "$JAIL_NAME"

echo "[INFO] Setup completed for $TARGET_ENV."
