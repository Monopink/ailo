#!/bin/bash
# Database initialization script for Docker container
# This script is automatically executed by PostgreSQL Docker container on first startup

set -e

# Determine environment (default to dev)
ENV=${ENVIRONMENT:-dev}

echo "========================================="
echo "Database Initialization Starting"
echo "========================================="
echo "Database: $POSTGRES_DB"
echo "User: $POSTGRES_USER"
echo "Environment: $ENV"
echo "Load Sample Data: ${LOAD_SAMPLE_DATA:-false}"
echo "========================================="

# Load database schema
echo ""
echo "[1/3] Loading database schema..."
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
	\i /docker-entrypoint-initdb.d/01_schema.sql
EOSQL
echo "✓ Schema loaded successfully"

# Load required system data based on environment
echo ""
echo "[2/3] Loading required system data for $ENV environment..."
case "$ENV" in
    prod|production)
        psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
			\i /docker-entrypoint-initdb.d/02_required_data_prod.sql
EOSQL
        ;;
    test)
        psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
			\i /docker-entrypoint-initdb.d/02_required_data_test.sql
EOSQL
        ;;
    dev|development|*)
        psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
			\i /docker-entrypoint-initdb.d/02_required_data.sql
EOSQL
        ;;
esac
echo "✓ Required data loaded successfully"

# Optionally load sample data (only for dev/test environment or if explicitly requested)
echo ""
if [ "$ENV" = "prod" ] || [ "$ENV" = "production" ]; then
    echo "[3/3] Skipping sample data (production environment)"
elif [ "$LOAD_SAMPLE_DATA" = "true" ] || [ "$ENV" = "dev" ] || [ "$ENV" = "development" ]; then
    echo "[3/3] Loading sample data..."
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
		\i /docker-entrypoint-initdb.d/03_sample_data.sql
EOSQL
    echo "✓ Sample data loaded successfully"
else
    echo "[3/3] Skipping sample data"
fi

echo ""
echo "========================================="
echo "Database Initialization Completed"
echo "========================================="

