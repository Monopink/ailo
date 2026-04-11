#!/bin/bash
# Generate nginx basic auth file for staging/prod with bcrypt hashing.
# Usage: ./generate-basic-auth.sh <staging|prod> [username] [--target admin|logs]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

TARGET_ENV="${1:-}"
shift || true
USERNAME="admin"
TARGET_KIND="admin"

if [[ "${1:-}" != "" && "${1:-}" != "--target" ]]; then
    USERNAME="$1"
    shift
fi

while [[ $# -gt 0 ]]; do
    case "$1" in
        --target)
            if [[ -z "${2:-}" ]]; then
                echo "--target requires value: admin or logs"
                exit 1
            fi
            TARGET_KIND="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 <staging|prod> [username] [--target admin|logs]"
            exit 1
            ;;
    esac
done

if [[ -z "$TARGET_ENV" || ( "$TARGET_ENV" != "staging" && "$TARGET_ENV" != "prod" ) ]]; then
    echo "Usage: $0 <staging|prod> [username] [--target admin|logs]"
    exit 1
fi

if [[ "$TARGET_KIND" != "admin" && "$TARGET_KIND" != "logs" ]]; then
    echo "Usage: $0 <staging|prod> [username] [--target admin|logs]"
    exit 1
fi

if ! command -v htpasswd >/dev/null 2>&1; then
    echo "htpasswd is required but not found (install apache2-utils or httpd-tools)"
    exit 1
fi

TARGET_DIR="$PROJECT_DIR/deployment/$TARGET_ENV/secrets"
TARGET_FILE="$TARGET_DIR/.htpasswd"
if [[ "$TARGET_KIND" == "logs" ]]; then
    TARGET_FILE="$TARGET_DIR/.htpasswd_logs"
fi
mkdir -p "$TARGET_DIR"

# -c: create file
# -B: bcrypt
# -C 12: bcrypt cost factor
htpasswd -cBC 12 "$TARGET_FILE" "$USERNAME"

# Nginx worker process inside container must be able to read the file.
# The file contains bcrypt hashes (not plaintext), so readability is acceptable here.
chmod 644 "$TARGET_FILE"

echo "Generated: $TARGET_FILE"
