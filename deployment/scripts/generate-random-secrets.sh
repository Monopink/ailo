#!/bin/bash
# Generate random secrets for staging/prod without printing plaintext to terminal.
# Usage:
#   ./generate-random-secrets.sh <staging|prod> [--no-apply-env] [--basic-auth-user USER]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

TARGET_ENV="${1:-}"
if [[ -z "$TARGET_ENV" || ( "$TARGET_ENV" != "staging" && "$TARGET_ENV" != "prod" ) ]]; then
    echo "Usage: $0 <staging|prod> [--no-apply-env] [--basic-auth-user USER]"
    exit 1
fi

APPLY_ENV=true
BASIC_AUTH_USER=""
shift || true
while [[ $# -gt 0 ]]; do
    case "$1" in
        --no-apply-env)
            APPLY_ENV=false
            shift
            ;;
        --basic-auth-user)
            if [[ -z "${2:-}" ]]; then
                echo "--basic-auth-user requires a username"
                exit 1
            fi
            BASIC_AUTH_USER="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

ENV_FILE="$PROJECT_DIR/deployment/$TARGET_ENV/.env"
SECRETS_DIR="$PROJECT_DIR/deployment/$TARGET_ENV/secrets"
GENERATED_FILE="$SECRETS_DIR/.generated-secrets.env"
HTPASSWD_FILE="$SECRETS_DIR/.htpasswd"

if [[ ! -f "$ENV_FILE" ]]; then
    echo "Environment file not found: $ENV_FILE"
    exit 1
fi

if ! command -v openssl >/dev/null 2>&1; then
    echo "openssl is required but not found"
    exit 1
fi

mkdir -p "$SECRETS_DIR"
umask 077

gen_secret() {
    openssl rand -base64 48 | tr -d '\n' | tr '/+' '_-'
}

POSTGRES_PASSWORD="$(gen_secret)"
JWT_SECRET_KEY="$(gen_secret)"
ADMIN_SECRET_KEY="$(gen_secret)"
BASIC_AUTH_PASSWORD="$(gen_secret)"

# Keep DB app password equal to POSTGRES_PASSWORD to avoid mismatch.
DB_PASSWORD="$POSTGRES_PASSWORD"

cat > "$GENERATED_FILE" <<EOF
# Generated at: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
POSTGRES_PASSWORD=$POSTGRES_PASSWORD
DB_PASSWORD=$DB_PASSWORD
JWT_SECRET_KEY=$JWT_SECRET_KEY
ADMIN_SECRET_KEY=$ADMIN_SECRET_KEY
BASIC_AUTH_PASSWORD=$BASIC_AUTH_PASSWORD
EOF
chmod 600 "$GENERATED_FILE"

if [[ "$APPLY_ENV" == "true" ]]; then
    sed -i "s#^POSTGRES_PASSWORD=.*#POSTGRES_PASSWORD=$POSTGRES_PASSWORD#" "$ENV_FILE"
    sed -i "s#^DB_PASSWORD=.*#DB_PASSWORD=$DB_PASSWORD#" "$ENV_FILE"
    sed -i "s#^JWT_SECRET_KEY=.*#JWT_SECRET_KEY=$JWT_SECRET_KEY#" "$ENV_FILE"
    sed -i "s#^ADMIN_SECRET_KEY=.*#ADMIN_SECRET_KEY=$ADMIN_SECRET_KEY#" "$ENV_FILE"
fi

if [[ -n "$BASIC_AUTH_USER" ]]; then
    if ! command -v htpasswd >/dev/null 2>&1; then
        echo "htpasswd is required but not found (install apache2-utils or httpd-tools)"
        exit 1
    fi
    printf '%s\n' "$BASIC_AUTH_PASSWORD" | htpasswd -i -c -B -C 12 "$HTPASSWD_FILE" "$BASIC_AUTH_USER" >/dev/null
    chmod 600 "$HTPASSWD_FILE"
fi

echo "Generated secrets file: $GENERATED_FILE"
echo "Applied env updates: $APPLY_ENV ($ENV_FILE)"
if [[ -n "$BASIC_AUTH_USER" ]]; then
    echo "Generated htpasswd: $HTPASSWD_FILE (user: $BASIC_AUTH_USER)"
else
    echo "htpasswd not generated (use --basic-auth-user USER if needed)"
fi
echo "Plaintext secrets were NOT printed. Read them only from secured file."
