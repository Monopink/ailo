#!/bin/bash

# Simple monitoring script for Says AI Chat App
# Usage: ./monitor.sh [check|webhook-test]

set -e

# Configuration
COMPOSE_FILE="docker-compose.prod.yml"
WEBHOOK_URL=""  # Set your webhook URL here (DingTalk, WeChat Work, etc.)
LOG_FILE="../logs/monitor.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Functions
log_info() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] INFO:${NC} $1" | tee -a "$LOG_FILE"
}

log_warning() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1" | tee -a "$LOG_FILE"
}

send_webhook() {
    local message="$1"
    local level="$2"
    
    if [ -z "$WEBHOOK_URL" ]; then
        log_warning "Webhook URL not configured, skipping notification"
        return
    fi
    
    # Generic webhook format (adapt for specific platforms)
    local payload="{\"text\":\"[Says Monitor] [$level] $message\"}"
    
    curl -s -X POST "$WEBHOOK_URL" \
        -H "Content-Type: application/json" \
        -d "$payload" || log_error "Failed to send webhook notification"
}

check_service_health() {
    local service="$1"
    local status=$(docker-compose -f $COMPOSE_FILE ps -q $service 2>/dev/null)
    
    if [ -z "$status" ]; then
        log_error "Service $service is not running"
        send_webhook "Service $service is DOWN" "ERROR"
        return 1
    fi
    
    local health=$(docker inspect --format='{{.State.Health.Status}}' $(docker-compose -f $COMPOSE_FILE ps -q $service) 2>/dev/null || echo "unknown")
    
    if [ "$health" = "unhealthy" ]; then
        log_error "Service $service is unhealthy"
        send_webhook "Service $service is UNHEALTHY" "ERROR"
        return 1
    fi
    
    log_info "Service $service is healthy"
    return 0
}

check_disk_space() {
    local usage=$(df / | awk 'NR==2 {print $5}' | sed 's/%//')
    
    if [ "$usage" -gt 90 ]; then
        log_error "Disk usage is ${usage}% (critical)"
        send_webhook "Disk usage critical: ${usage}%" "ERROR"
        return 1
    elif [ "$usage" -gt 80 ]; then
        log_warning "Disk usage is ${usage}% (warning)"
        send_webhook "Disk usage warning: ${usage}%" "WARNING"
        return 1
    fi
    
    log_info "Disk usage is ${usage}% (normal)"
    return 0
}

check_memory_usage() {
    local usage=$(free | awk 'NR==2{printf "%.0f", $3*100/$2}')
    
    if [ "$usage" -gt 90 ]; then
        log_error "Memory usage is ${usage}% (critical)"
        send_webhook "Memory usage critical: ${usage}%" "ERROR"
        return 1
    elif [ "$usage" -gt 80 ]; then
        log_warning "Memory usage is ${usage}% (warning)"
        send_webhook "Memory usage warning: ${usage}%" "WARNING"
        return 1
    fi
    
    log_info "Memory usage is ${usage}% (normal)"
    return 0
}

check_ssl_certificate() {
    local domain=$(grep "DOMAIN=" ../backend/.env.prod | cut -d'=' -f2)
    
    if [ -z "$domain" ]; then
        log_warning "Domain not found in environment file"
        return 1
    fi
    
    local expiry=$(echo | openssl s_client -servername $domain -connect $domain:443 2>/dev/null | openssl x509 -noout -dates | grep notAfter | cut -d'=' -f2)
    local expiry_epoch=$(date -d "$expiry" +%s 2>/dev/null || echo "0")
    local current_epoch=$(date +%s)
    local days_left=$(( (expiry_epoch - current_epoch) / 86400 ))
    
    if [ "$days_left" -lt 7 ]; then
        log_error "SSL certificate expires in $days_left days"
        send_webhook "SSL certificate expires in $days_left days" "ERROR"
        return 1
    elif [ "$days_left" -lt 30 ]; then
        log_warning "SSL certificate expires in $days_left days"
        send_webhook "SSL certificate expires in $days_left days" "WARNING"
        return 1
    fi
    
    log_info "SSL certificate is valid for $days_left days"
    return 0
}

run_health_check() {
    log_info "Starting health check..."
    
    local failed=0
    
    # Check services
    services=("mysql_db" "accounts_service" "contacts_service" "bot_message_service" "web" "nginx")
    for service in "${services[@]}"; do
        check_service_health "$service" || failed=$((failed + 1))
    done
    
    # Check system resources
    check_disk_space || failed=$((failed + 1))
    check_memory_usage || failed=$((failed + 1))
    
    # Check SSL certificate
    check_ssl_certificate || failed=$((failed + 1))
    
    if [ "$failed" -eq 0 ]; then
        log_info "All health checks passed"
    else
        log_error "$failed health check(s) failed"
        return 1
    fi
}

test_webhook() {
    log_info "Testing webhook notification..."
    send_webhook "Monitor webhook test - $(date)" "INFO"
    log_info "Webhook test completed"
}

# Create logs directory
mkdir -p ../logs

# Main script logic
case "${1:-check}" in
    "check")
        run_health_check
        ;;
    "webhook-test")
        test_webhook
        ;;
    "help"|*)
        echo "Usage: $0 {check|webhook-test}"
        echo ""
        echo "Commands:"
        echo "  check        - Run health checks"
        echo "  webhook-test - Test webhook notification"
        echo ""
        echo "Configuration:"
        echo "  Set WEBHOOK_URL in this script for notifications"
        echo ""
        echo "Cron example (every 5 minutes):"
        echo "  */5 * * * * /path/to/monitor.sh check"
        ;;
esac
