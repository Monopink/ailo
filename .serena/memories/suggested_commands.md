# Development Commands and Workflow

## Environment Setup

### Start Development Environment
```bash
cd deployment
docker-compose up -d
```

### Frontend Development
```bash
cd frontend/admin
pnpm install  # Install dependencies
pnpm dev      # Start development server (port 5174)
```

## Database Operations

### Database Connection
- **Host**: localhost:5432
- **Database**: PostgreSQL 16
- **Init Scripts**: `backend/database/init/init.sql`
- **Models**: `backend/app/models/`

### Migration Commands
```bash
# Apply database migrations
cd backend
python migrate.py
```

## Testing Commands

### Backend Testing
```bash
cd backend/app
pytest                    # Run all tests
pytest tests/             # Run specific test directory
pytest -v                 # Verbose output
```

### API Testing
```bash
# Health check
curl http://localhost:8000/health

# Admin panel access
# URL: http://localhost:8000/qiao-dash/
# Credentials: admin/admin123
```

## Development Workflow

### Code Quality
```bash
# Install linting tools (if not in requirements)
pip install flake8 black isort mypy

# Code formatting
black backend/app/
isort backend/app/

# Linting
flake8 backend/app/

# Type checking
mypy backend/app/
```

### Logging and Monitoring
- **Log Directory**: `logs/`
- **Log Level**: Configured via environment variables
- **Structured Logging**: Using structlog with JSON format
- **Service Name**: "backend"

## Common Development Tasks

### AI Character Testing
1. Access admin panel: http://localhost:8000/qiao-dash/
2. Navigate to AI Characters
3. Click "Test" button for any character
4. Use LLM configuration dropdown + test message input

### Database Inspection
```bash
# Connect to PostgreSQL
docker exec -it postgres_db_container psql -U postgres -d says_db

# Common queries
\dt                       # List tables
\d ai_characters         # Describe table structure
SELECT * FROM ai_characters LIMIT 5;
```

### Service Debugging
```bash
# View backend logs
docker logs backend_container -f

# View database logs  
docker logs postgres_db_container -f

# Check service status
docker-compose ps
```