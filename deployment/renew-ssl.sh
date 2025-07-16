#!/bin/bash

# SSL certificate renewal script
# This script should be run via cron job to automatically renew SSL certificates

set -e

# Configuration
COMPOSE_FILE="docker-compose.prod.yml"
LOG_FILE="/var/log/ssl-renewal.log"

# Logging function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a $LOG_FILE
}

log "Starting SSL certificate renewal process..."

# Check if docker-compose file exists
if [ ! -f "$COMPOSE_FILE" ]; then
    log "ERROR: $COMPOSE_FILE not found"
    exit 1
fi

# Attempt to renew certificates
log "Attempting to renew SSL certificates..."
if docker-compose -f $COMPOSE_FILE run --rm certbot renew --quiet; then
    log "Certificate renewal successful"

    # Reload nginx to use new certificates
    log "Reloading nginx configuration..."
    if docker-compose -f $COMPOSE_FILE exec nginx nginx -s reload; then
        log "Nginx reloaded successfully"
    else
        log "ERROR: Failed to reload nginx"
        exit 1
    fi
else
    log "Certificate renewal failed or not needed"
fi

log "SSL renewal process completed"
