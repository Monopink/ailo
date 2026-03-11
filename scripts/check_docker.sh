#!/bin/bash
# ============================================================================
# Docker Container Health Check Script
# ============================================================================
# This script checks the health status of Docker containers and services.
# Usage:
#   ./scripts/check_docker.sh
# ============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
DEPLOYMENT_DIR="deployment"
POSTGRES_CONTAINER="postgres"
BACKEND_CONTAINER="backend"
BACKEND_URL="http://localhost:8000"
HEALTH_ENDPOINT="${BACKEND_URL}/health"
MAX_WAIT_TIME=30

# Helper functions
print_header() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

# Check if Docker is running
check_docker_running() {
    print_header "1. Checking Docker Status"

    if ! docker info > /dev/null 2>&1; then
        print_error "Docker is not running"
        echo ""
        print_info "Please start Docker Desktop and try again"
        return 1
    fi

    print_success "Docker is running"
    return 0
}

# Check if containers exist and are running
check_containers() {
    print_header "2. Checking Container Status"

    local all_running=0

    # Check PostgreSQL container
    if docker ps --format '{{.Names}}' | grep -q "^${POSTGRES_CONTAINER}$"; then
        local status=$(docker inspect --format='{{.State.Status}}' "$POSTGRES_CONTAINER")
        if [ "$status" = "running" ]; then
            print_success "PostgreSQL container is running"
        else
            print_error "PostgreSQL container exists but is not running (status: $status)"
            all_running=1
        fi
    else
        print_error "PostgreSQL container not found"
        all_running=1
    fi

    # Check Backend container
    if docker ps --format '{{.Names}}' | grep -q "^${BACKEND_CONTAINER}$"; then
        local status=$(docker inspect --format='{{.State.Status}}' "$BACKEND_CONTAINER")
        if [ "$status" = "running" ]; then
            print_success "Backend container is running"
        else
            print_error "Backend container exists but is not running (status: $status)"
            all_running=1
        fi
    else
        print_error "Backend container not found"
        all_running=1
    fi

    if [ $all_running -ne 0 ]; then
        echo ""
        print_info "To start containers, run: docker compose -f deployment/dev/compose.yaml up -d"
        return 1
    fi

    return 0
}

# Check PostgreSQL health
check_postgres_health() {
    print_header "3. Checking PostgreSQL Health"

    if ! docker ps --format '{{.Names}}' | grep -q "^${POSTGRES_CONTAINER}$"; then
        print_error "PostgreSQL container not running, skipping health check"
        return 1
    fi

    # Check container health status
    local health_status=$(docker inspect --format='{{.State.Health.Status}}' "$POSTGRES_CONTAINER" 2>/dev/null || echo "none")

    if [ "$health_status" = "healthy" ]; then
        print_success "PostgreSQL health check passed"
    elif [ "$health_status" = "none" ]; then
        # No healthcheck defined, try direct connection
        if docker exec "$POSTGRES_CONTAINER" pg_isready -U ailo_user -d ailo > /dev/null 2>&1; then
            print_success "PostgreSQL is accepting connections"
        else
            print_error "PostgreSQL is not ready"
            return 1
        fi
    else
        print_error "PostgreSQL health check failed (status: $health_status)"
        return 1
    fi

    return 0
}

# Check backend API health
check_backend_health() {
    print_header "4. Checking Backend API Health"

    if ! docker ps --format '{{.Names}}' | grep -q "^${BACKEND_CONTAINER}$"; then
        print_error "Backend container not running, skipping health check"
        return 1
    fi

    print_info "Waiting for backend to be ready (max ${MAX_WAIT_TIME}s)..."

    local elapsed=0
    local interval=2

    while [ $elapsed -lt $MAX_WAIT_TIME ]; do
        if curl -s -f "$HEALTH_ENDPOINT" > /dev/null 2>&1; then
            print_success "Backend API is responding"

            # Get detailed health info
            local health_response=$(curl -s "$HEALTH_ENDPOINT")
            echo ""
            echo "Health check response:"
            echo "$health_response" | python -m json.tool 2>/dev/null || echo "$health_response"
            return 0
        fi

        sleep $interval
        elapsed=$((elapsed + interval))
        echo -n "."
    done

    echo ""
    print_error "Backend API is not responding after ${MAX_WAIT_TIME}s"
    echo ""
    print_info "Check backend logs: docker logs $BACKEND_CONTAINER"
    return 1
}

# Show container logs summary
show_logs_summary() {
    print_header "5. Recent Container Logs"

    if docker ps --format '{{.Names}}' | grep -q "^${BACKEND_CONTAINER}$"; then
        echo ""
        echo -e "${BLUE}Backend logs (last 10 lines):${NC}"
        docker logs --tail 10 "$BACKEND_CONTAINER" 2>&1 | sed 's/^/  /'
    fi

    if docker ps --format '{{.Names}}' | grep -q "^${POSTGRES_CONTAINER}$"; then
        echo ""
        echo -e "${BLUE}PostgreSQL logs (last 5 lines):${NC}"
        docker logs --tail 5 "$POSTGRES_CONTAINER" 2>&1 | sed 's/^/  /'
    fi
}

# Main execution
main() {
    echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║   Docker Health Check Script          ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"

    local failed=0

    # Run all checks
    check_docker_running || failed=1

    if [ $failed -eq 0 ]; then
        check_containers || failed=1
    fi

    if [ $failed -eq 0 ]; then
        check_postgres_health || failed=1
        check_backend_health || failed=1
    fi

    # Always show logs summary if containers exist
    if docker ps -a --format '{{.Names}}' | grep -q -E "^(${POSTGRES_CONTAINER}|${BACKEND_CONTAINER})$"; then
        show_logs_summary
    fi

    # Summary
    print_header "Health Check Summary"

    if [ $failed -eq 0 ]; then
        echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
        echo -e "${GREEN}║   ✓ ALL CHECKS PASSED!                ║${NC}"
        echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
        echo ""
        print_success "All services are healthy and running"
        exit 0
    else
        echo -e "${RED}╔════════════════════════════════════════╗${NC}"
        echo -e "${RED}║   ✗ HEALTH CHECK FAILED               ║${NC}"
        echo -e "${RED}╚════════════════════════════════════════╝${NC}"
        echo ""
        print_error "Some services are not healthy"
        echo ""
        print_info "Common solutions:"
        echo "  1. Start Docker Desktop"
        echo "  2. Start containers: docker compose -f deployment/dev/compose.yaml up -d"
        echo "  3. Check logs: docker logs <container_name>"
        echo "  4. Restart containers: docker compose -f deployment/dev/compose.yaml restart"
        exit 1
    fi
}

# Run main
main
