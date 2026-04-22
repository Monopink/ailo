#!/bin/bash
# Database infrastructure initialization script for Docker container

set -euo pipefail

ENV=${ENVIRONMENT:-dev}

echo "========================================="
echo "Database Infrastructure Initialization Starting"
echo "========================================="
echo "Database: $POSTGRES_DB"
echo "User: $POSTGRES_USER"
echo "Environment: $ENV"
echo "========================================="

echo ""
echo "[1/1] Applying infrastructure SQL..."
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<'EOSQL'
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
EOSQL
echo "✓ Infrastructure SQL applied successfully"

echo ""
echo "========================================="
echo "Database Infrastructure Initialization Completed"
echo "========================================="
