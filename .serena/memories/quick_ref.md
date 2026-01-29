# Quick Reference

## Docker

**Container Names**: `backend`, `postgres`

**Common Commands**:
```bash
# Start/restart
cd deployment && docker-compose up -d
docker-compose restart backend

# Logs
docker logs backend -f

# Rebuild (after requirements.txt change)
docker-compose build backend && docker-compose up -d backend
```

---

## Database

**Connection**: `localhost:5432`, user `postgres`, see `.env` for password/database

**Access**:
```bash
docker exec -it postgres_db_container psql -U postgres -d <db_name>
```

---

## Backend

**URLs**:
- API: http://localhost:8000
- Admin: http://localhost:8000/qiao-dash/ (admin/admin123)
- Docs: http://localhost:8000/docs

**Tests**:
```bash
cd backend && pytest
```

---

## WeChat Mini-Program

**Commands**:
```bash
cd frontend/wx-minipg
npm run check          # All checks (type + lint + style + ui)
npm run lint:fix       # Auto-fix ESLint errors
```
