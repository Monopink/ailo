#!/bin/bash
# Generate nginx basic auth file for staging/prod with bcrypt hashing.
# Usage: ./generate-basic-auth.sh <staging|prod> [username]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

TARGET_ENV="${1:-}"
USERNAME="${2:-admin}"

if [[ -z "$TARGET_ENV" || ( "$TARGET_ENV" != "staging" && "$TARGET_ENV" != "prod" ) ]]; then
    echo "Usage: $0 <staging|prod> [username]"
    exit 1
fi

if ! command -v htpasswd >/dev/null 2>&1; then
    echo "htpasswd is required but not found (install apache2-utils or httpd-tools)"
    exit 1
fi

TARGET_DIR="$PROJECT_DIR/deployment/$TARGET_ENV/secrets"
TARGET_FILE="$TARGET_DIR/.htpasswd"
mkdir -p "$TARGET_DIR"

# -c: create file
# -B: bcrypt
# -C 12: bcrypt cost factor
htpasswd -cBC 12 "$TARGET_FILE" "$USERNAME"

# Nginx worker process inside container must be able to read the file.
# The file contains bcrypt hashes (not plaintext), so readability is acceptable here.
chmod 644 "$TARGET_FILE"

echo "Generated: $TARGET_FILE"
