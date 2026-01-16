# Database Reset Workflow

Detailed steps for safely resetting database to clean state.

## Configuration

**Read from**:
- Database: `deployment/.env` (POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD, LOAD_SAMPLE_DATA)
- Docker: `deployment/docker-compose.yml`
- Init scripts: `backend/database/init/`

**Verify before starting**:
```bash
cd deployment
grep -E "POSTGRES_DB|POSTGRES_USER|LOAD_SAMPLE_DATA" .env
```

## Safety Warning

**⚠️ DANGER**: This operation is **DESTRUCTIVE** and will:
- Drop the entire database
- Delete all data permanently
- Recreate schema from init scripts
- Load seed data (if configured)

**Never run this on production!** Only use in development/test environments.

## Reset Workflow

### Step 1: Confirm with User

**ALWAYS ask for explicit confirmation** before proceeding:

```
⚠️ WARNING: This will DELETE ALL DATA in the database.
Are you sure you want to reset the database? (yes/no)
```

Do NOT proceed unless user explicitly confirms with "yes".

### Step 2: Check Environment

Verify we're not in production:

```bash
cd deployment
grep -E "POSTGRES_DB|COMPOSE_PROJECT_NAME" .env
```

**STOP immediately if**:
- POSTGRES_DB contains "production" or "prod"
- COMPOSE_PROJECT_NAME contains "prod" or "production"
- Any indication this is a production system

### Step 3: Stop Backend Service

Stop backend to close all database connections:

```bash
cd deployment
docker-compose stop backend
```

### Step 4: Drop and Recreate Database

Drop existing database and create new one:

```bash
cd deployment
docker-compose exec postgres psql -U $POSTGRES_USER -c "DROP DATABASE IF EXISTS $POSTGRES_DB;"
docker-compose exec postgres psql -U $POSTGRES_USER -c "CREATE DATABASE $POSTGRES_DB;"
```

**Note**: Uses environment variables from `.env` file.

### Step 5: Run Official Initialization Script

**IMPORTANT**: Use official `00_init_database.sh` script:

```bash
cd deployment
docker-compose exec postgres bash /docker-entrypoint-initdb.d/00_init_database.sh
```

**Why use this script?**
- Automatically handles environment-specific data loading
- Respects `LOAD_SAMPLE_DATA` environment variable
- Loads correct data files based on environment (dev/test/prod)
- Provides clear progress output

**Script execution order** (handled automatically):
1. `01_schema.sql` - Creates tables, indexes, constraints
2. `02_required_data*.sql` - Loads required system data (environment-specific)
3. `03_sample_data.sql` - Loads sample data (if LOAD_SAMPLE_DATA=true)

### Step 6: Verify Database State

Check database was initialized correctly:

```bash
cd deployment
# List all tables
docker-compose exec postgres psql -U $POSTGRES_USER -d $POSTGRES_DB -c "\dt"

# Check table schemas
docker-compose exec postgres psql -U $POSTGRES_USER -d $POSTGRES_DB -c "\d+ users"
docker-compose exec postgres psql -U $POSTGRES_USER -d $POSTGRES_DB -c "\d+ personas"

# Count rows in key tables
docker-compose exec postgres psql -U $POSTGRES_USER -d $POSTGRES_DB -c "SELECT COUNT(*) FROM users;"
```

**Verify**:
- All expected tables exist
- Tables have correct columns and types
- Seed data is loaded (if applicable)
- No errors in output

### Step 7: Update Alembic Version

Mark database as up-to-date with migrations:

```bash
cd deployment
# Stamp database with latest migration
docker-compose exec backend alembic stamp head
```

This tells Alembic that database is at latest version.

### Step 8: Restart Backend Service

Start backend service:

```bash
cd deployment
docker-compose start backend

# Wait for service to be healthy
docker-compose ps backend
```

### Step 9: Test Database Connection

Verify backend can connect to database:

```bash
cd deployment
# Check backend logs
docker-compose logs backend | tail -20

# Test API health endpoint
curl http://localhost:8000/health
```

**Expected**: Backend starts successfully and can query database.

## Important Rules

1. **Always confirm with user** - Never reset database without explicit confirmation
2. **Check environment first** - Never run on production
3. **Stop backend before dropping** - Prevents connection errors
4. **Run scripts in order** - Schema before seed data
5. **Stamp Alembic version** - Keeps migration history consistent
6. **Verify after reset** - Ensure database is in correct state

## Common Issues

### Issue: "database is being accessed by other users"

**Cause**: Backend or other connections still open

**Solution**:
```bash
cd deployment
# Force disconnect all users
docker-compose exec postgres psql -U $POSTGRES_USER -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$POSTGRES_DB';"
# Then retry drop database
```

### Issue: Init script fails with syntax error

**Cause**: SQL syntax error in init script

**Solution**: Check error message, fix SQL in `backend/database/init/*.sql`, and retry

### Issue: "relation already exists"

**Cause**: Database wasn't fully dropped

**Solution**:
```bash
cd deployment
docker-compose exec postgres psql -U $POSTGRES_USER -d $POSTGRES_DB -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
```

### Issue: Alembic version mismatch after reset

**Cause**: Forgot to stamp Alembic version

**Solution**:
```bash
cd deployment
docker-compose exec backend alembic stamp head
```

### Issue: Seed data fails to load

**Cause**: Foreign key constraints or missing dependencies

**Solution**: Check seed data order, ensure referenced records exist first

## Reference

- Init script: `backend/database/init/00_init_database.sh`
- Docker Compose: `deployment/docker-compose.yml`
- Environment example: `deployment/.env.example`
