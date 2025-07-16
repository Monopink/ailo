#!/bin/bash

# Production deployment script for Says AI Chat App
# Usage: ./deploy.sh [start|stop|restart|logs|status|ssl|update]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
COMPOSE_FILE="docker-compose.prod.yml"
ENV_FILE="../backend/.env.prod"

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}



check_requirements() {
    log_info "Checking requirements..."

    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed"
        exit 1
    fi

    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose is not installed"
        exit 1
    fi
    
    if [ ! -f "$ENV_FILE" ]; then
        log_error "Environment file $ENV_FILE not found"
        exit 1
    fi
    
    log_success "Requirements check passed"
}



start_services() {
    log_info "Starting services..."
    check_requirements

    # Create necessary directories
    mkdir -p ../nginx/ssl
    mkdir -p ../logs

    # Start services
    docker-compose -f $COMPOSE_FILE up -d

    # Wait for services to be ready
    log_info "Waiting for services to be ready..."
    sleep 30

    # Check service health
    check_services

    log_success "Services started successfully"
}

setup_ssl() {
    log_info "Setting up SSL certificates..."
    
    # Check if nginx is running
    if ! docker-compose -f $COMPOSE_FILE ps nginx | grep -q "Up"; then
        log_error "Nginx service is not running. Run './deploy.sh init' first"
        exit 1
    fi
    
    # Request SSL certificate
    log_info "Requesting SSL certificate for $DOMAIN..."
    docker-compose -f $COMPOSE_FILE run --rm certbot
    
    if [ $? -eq 0 ]; then
        log_success "SSL certificate obtained successfully"
        
        # Restart nginx to load SSL configuration
        log_info "Restarting nginx with SSL configuration..."
        docker-compose -f $COMPOSE_FILE restart nginx
        
        log_success "SSL setup completed"
    else
        log_error "Failed to obtain SSL certificate"
        log_warning "Make sure:"
        log_warning "1. Domain $DOMAIN points to this server"
        log_warning "2. Ports 80 and 443 are open"
        log_warning "3. No other services are using these ports"
        exit 1
    fi
}

update_deployment() {
    log_info "Updating deployment..."
    check_requirements

    # Rebuild and restart services
    log_info "Rebuilding services..."
    docker-compose -f $COMPOSE_FILE build
    docker-compose -f $COMPOSE_FILE up -d

    # Clean up unused images
    log_info "Cleaning up unused Docker images..."
    docker image prune -f

    log_success "Deployment updated successfully"
}

check_services() {
    log_info "Checking service health..."
    
    services=("mysql_db" "accounts_service" "contacts_service" "bot_message_service" "web" "nginx")
    
    for service in "${services[@]}"; do
        if docker-compose -f $COMPOSE_FILE ps $service | grep -q "Up"; then
            log_success "$service is running"
        else
            log_error "$service is not running"
        fi
    done
}

show_logs() {
    service=${2:-""}
    if [ -n "$service" ]; then
        log_info "Showing logs for $service..."
        docker-compose -f $COMPOSE_FILE logs -f $service
    else
        log_info "Showing logs for all services..."
        docker-compose -f $COMPOSE_FILE logs -f
    fi
}

restart_services() {
    log_info "Restarting all services..."
    docker-compose -f $COMPOSE_FILE restart
    log_success "All services restarted"
}

stop_services() {
    log_info "Stopping all services..."
    docker-compose -f $COMPOSE_FILE down
    log_success "All services stopped"
}

# Main script logic
case "${1:-help}" in
    "start")
        start_services
        ;;
    "stop")
        stop_services
        ;;
    "restart")
        restart_services
        ;;
    "logs")
        show_logs $@
        ;;
    "status")
        check_services
        ;;
    "ssl")
        setup_ssl
        ;;
    "update")
        update_deployment
        ;;
    "help"|*)
        echo "Usage: $0 {start|stop|restart|logs|status|ssl|update}"
        echo ""
        echo "Commands:"
        echo "  start    - Start all services"
        echo "  stop     - Stop all services"
        echo "  restart  - Restart all services"
        echo "  logs     - Show logs (optionally specify service name)"
        echo "  status   - Check service status"
        echo "  ssl      - Setup SSL certificates"
        echo "  update   - Update deployment with latest code"
        echo ""
        echo "Example:"
        echo "  $0 start         # Start services"
        echo "  $0 logs nginx    # Show nginx logs"
        ;;
esac
