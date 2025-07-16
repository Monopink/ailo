# Deployment Configuration

## Environment Setup

### Development Environment

```bash
# Start all services
./start.sh
# or
docker-compose up -d
```

### Production Environment  

```bash
docker-compose -f docker-compose.prod.yml up -d
```

### Stable Version

```bash
docker-compose -f docker-compose.stable.yml up -d
```

## Service Ports

### Internal Container Ports

- **accounts_service**: 8000 (internal) → 8001 (host)
- **contacts_service**: 8000 (internal) → 8002 (host)
- **bot_message_service**: 8000 (internal) → 8003 (host)
- **frontend**: 5173 (internal) → 5173 (host)
- **mysql**: 3306 (internal) → 33061 (host)

### Development Tools

- **Web Dev Frontend**: 8080
- **Dozzle Log Viewer**: 9999
- **ngrok Web Interface**: 4040

## Environment Variables

### Required Variables

```env
# Database
MYSQL_ROOT_PASSWORD=
MYSQL_DATABASE=
MYSQL_USER=
MYSQL_PASSWORD=
MYSQL_PORT=3306

# LeanCloud
LEANCLOUD_APP_ID=
LEANCLOUD_APP_KEY=
LEANCLOUD_MASTER_KEY=
LEANCLOUD_BASE_URL=

# Services
INTERNAL_SERVICE_KEY=
NGROK_AUTHTOKEN=

# Service Ports
ACCOUNTS_SERVICE_PORT=8001
CONTACTS_SERVICE_PORT=8002
BOT_MESSAGE_SERVICE_PORT=8003
```

### Configuration Files

- **Main Config**: `.env` in project root
- **Service Configs**: Each service has own config files
- **No Shared Config**: Services don't share configuration files

## Docker Configuration

### Network Setup

- **Network Name**: says-network
- **Driver**: bridge
- **Service Communication**: Internal Docker network

### Volume Management

- **Database Persistence**: mysql_data volume
- **Log Centralization**: ./logs/ directory mounted
- **Development Code**: Source code mounted for hot reload

### Container Dependencies

- **Database First**: MySQL starts before application services
- **Service Order**: accounts → contacts → bot_message → frontend
- **Health Checks**: Services wait for dependencies

## Development Tools

### ngrok Configuration

- **Purpose**: Expose bot_message_service webhook for LeanCloud
- **Authentication**: Requires NGROK_AUTHTOKEN
- **Web Interface**: <http://localhost:4040>
- **Target**: bot_message_service:8000

### Log Management

- **Dozzle**: Web-based log viewer at <http://localhost:9999>
- **Log Files**: Centralized in ./logs/ directory
- **Structured Logging**: JSON format for all services

## Database Setup

### MySQL Configuration

- **Version**: MySQL 8.0
- **Character Set**: utf8mb4
- **Collation**: utf8mb4_unicode_ci
- **Authentication**: caching_sha2_password

### Initialization

- **Schema**: database/init/init.sql
- **Test Data**: Included in initialization script
- **No Migrations**: Schema changes are breaking in MVP phase

## Testing Configuration

### Test Accounts

- **Phone**: 13800138002
- **Password**: 12345678
- **SMS Code**: Any 6-digit number (development)

### Health Check Endpoints

```bash
curl http://localhost:8001/health  # accounts_service
curl http://localhost:8002/health  # contacts_service
curl http://localhost:8003/health  # bot_message_service
```

## Troubleshooting

### Common Issues

1. **Port Conflicts**: Check if ports 8001-8003, 5173, 3306 are available
2. **Database Connection**: Verify MySQL container is running
3. **LeanCloud Config**: Check LEANCLOUD_* environment variables
4. **ngrok Token**: Verify NGROK_AUTHTOKEN is valid

### Service Restart

```bash
# Restart specific service
docker-compose restart accounts_service

# Rebuild and restart
docker-compose up -d --build accounts_service

# View logs
docker-compose logs -f accounts_service
```

### Database Reset

```bash
# Stop services
docker-compose down

# Remove database volume
docker volume rm says_mysql_data

# Restart (will reinitialize database)
docker-compose up -d
```

## Production Considerations

### Security

- **Environment Variables**: Use secure secret management
- **Network**: Restrict network access to necessary ports
- **Authentication**: Strong internal service keys
- **HTTPS**: Use HTTPS in production

### Monitoring

- **Health Checks**: Regular health check monitoring
- **Log Aggregation**: Centralized log collection
- **Error Tracking**: Error monitoring and alerting
- **Performance**: Response time and resource monitoring

### Scaling

- **Horizontal Scaling**: Services designed for horizontal scaling
- **Load Balancing**: Load balancer for multiple instances
- **Database**: Consider read replicas for scaling
- **Caching**: Redis for caching if needed
