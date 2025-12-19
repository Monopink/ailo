# Quick Reference

## Docker

### Container Names
```
backend_container       # FastAPI service
postgres_db_container   # PostgreSQL 16
minio_container        # MinIO object storage (if exists)
```

### Common Commands
```bash
# Start all services
cd deployment && docker-compose up -d

# Restart backend
docker-compose restart backend

# View logs
docker logs backend_container -f
docker logs postgres_db_container -f

# Rebuild image (after requirements.txt change)
docker-compose build backend
docker-compose up -d backend

# Clean and restart (CAUTION: data loss)
docker-compose down -v
docker-compose up -d
```

---

## Database

### Connection Info
```
Host: localhost
Port: 5432
Database: See .env file
User: postgres
Password: See .env file
```

### Connection Methods
```bash
# Via Docker
docker exec -it postgres_db_container psql -U postgres -d <db_name>

# Direct connection (needs local psql)
psql -h localhost -p 5432 -U postgres -d <db_name>
```

### Common Queries
```sql
-- View all tables
\dt

-- View table structure
\d table_name

-- View recent AI conversations
SELECT * FROM ai_conversations ORDER BY created_at DESC LIMIT 10;

-- View relationship scores
SELECT * FROM relationship_scores WHERE user_id = 'xxx';
```

---

## Backend

### Service URLs
```
API:         http://localhost:8000
Admin Panel: http://localhost:8000/qiao-dash/
Health:      http://localhost:8000/health
API Docs:    http://localhost:8000/docs
```

### Admin Credentials
```
Username: admin
Password: admin123
```

### Log Location
```
In container: /logs/
On host: deployment/logs/ (if mounted)
```

### Test Commands
```bash
cd backend
pytest                    # Run all tests
pytest tests/test_api/    # Run API tests
pytest -v -s              # Verbose output
```

---

## MinIO (If Deployed)

### Connection Info
```
Endpoint: http://localhost:9000
Console:  http://localhost:9001
Access Key: See .env (MINIO_ROOT_USER)
Secret Key: See .env (MINIO_ROOT_PASSWORD)
```

### Buckets
```
avatars      # User avatars
attachments  # Chat attachments
```

---

## Environment Variables

### Key Variables Location
```
.env                    # Root dir (production)
deployment/.env.example # Example template
```

### Required Variables
```bash
# Database
POSTGRES_PASSWORD=
DATABASE_URL=

# LeanCloud
LEANCLOUD_APP_ID=
LEANCLOUD_APP_KEY=
LEANCLOUD_MASTER_KEY=

# Doubao
DOUBAO_API_KEY=
DOUBAO_BASE_URL=

# MinIO (if used)
MINIO_ENDPOINT=
MINIO_ROOT_USER=
MINIO_ROOT_PASSWORD=
```

---

## WeChat Mini-Program

### Dev Tools
```
Project Dir: frontend/wx-minipg
AppID: See project.config.json
```

### Common Commands
```bash
cd frontend/wx-minipg
npm install              # Install dependencies
npm run compile          # Compile TypeScript
```

### Legal Domain Config
```
request:      https://your-backend.com
uploadFile:   https://your-backend.com
downloadFile: https://your-backend.com
```
