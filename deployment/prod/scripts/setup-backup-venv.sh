#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"

VENV_DIR="/opt/ailo-prod/venv/ailo-backup"
REQ_FILE="$PROJECT_DIR/deployment/prod/scripts/backup-requirements.txt"

if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: python3 is required but not found."
    exit 1
fi

if ! python3 -c "import ensurepip" >/dev/null 2>&1; then
    echo "ERROR: python3 venv support is missing (ensurepip unavailable)."
    echo "Install it and retry:"
    echo "  sudo apt-get update -y"
    echo "  sudo apt-get install -y python3.12-venv"
    exit 1
fi

python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --upgrade pip
"$VENV_DIR/bin/pip" install -r "$REQ_FILE"

echo "OK: venv created at $VENV_DIR"
