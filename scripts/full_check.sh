#!/bin/bash
# ============================================================================
# Full System Validation Script
# ============================================================================
# This script runs all validation checks: Docker health, code quality, and tests.
# This is the recommended script to run after making code changes.
#
# Usage:
#   ./scripts/full_check.sh              # Full validation
#   ./scripts/full_check.sh --quick      # Quick validation (modified files only)
#   ./scripts/full_check.sh --skip-docker # Skip Docker health check
#   ./scripts/full_check.sh --skip-tests  # Skip tests
# ============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
QUICK_MODE=false
SKIP_DOCKER=false
SKIP_TESTS=false
FAILED_CHECKS=()

# Helper functions
print_header() {
    echo -e "\n${CYAN}╔════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║ $1${NC}"
    echo -e "${CYAN}╚════════════════════════════════════════╝${NC}"
}

print_section() {
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

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --quick)
            QUICK_MODE=true
            shift
            ;;
        --skip-docker)
            SKIP_DOCKER=true
            shift
            ;;
        --skip-tests)
            SKIP_TESTS=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --quick        Quick mode (check modified files only)"
            echo "  --skip-docker  Skip Docker health check"
            echo "  --skip-tests   Skip test execution"
            echo "  --help         Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                    # Full validation"
            echo "  $0 --quick            # Quick validation"
            echo "  $0 --skip-docker      # Skip Docker check"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Run Docker health check
run_docker_check() {
    print_section "Step 1: Docker Health Check"

    if [ "$SKIP_DOCKER" = true ]; then
        print_warning "Skipping Docker health check (--skip-docker)"
        return 0
    fi

    if bash scripts/check_docker.sh; then
        print_success "Docker health check passed"
        return 0
    else
        print_error "Docker health check failed"
        FAILED_CHECKS+=("Docker Health Check")
        return 1
    fi
}

# Run code quality validation
run_code_validation() {
    print_section "Step 2: Code Quality Validation"

    local validate_args=""
    if [ "$QUICK_MODE" = true ]; then
        validate_args="--quick"
        print_info "Running in QUICK mode (modified files only)"
    fi

    if bash scripts/validate.sh $validate_args; then
        print_success "Code quality validation passed"
        return 0
    else
        print_error "Code quality validation failed"
        FAILED_CHECKS+=("Code Quality Validation")
        return 1
    fi
}

# Run tests
run_tests() {
    print_section "Step 3: Test Execution"

    if [ "$SKIP_TESTS" = true ]; then
        print_warning "Skipping tests (--skip-tests)"
        return 0
    fi

    local test_args="--fast"
    if [ "$QUICK_MODE" = false ]; then
        test_args=""
    fi

    if bash scripts/run_tests.sh $test_args; then
        print_success "All tests passed"
        return 0
    else
        print_error "Some tests failed"
        FAILED_CHECKS+=("Tests")
        return 1
    fi
}

# Main execution
main() {
    local start_time=$(date +%s)

    echo -e "${CYAN}╔════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║                                        ║${NC}"
    echo -e "${CYAN}║   Full System Validation Script       ║${NC}"
    echo -e "${CYAN}║                                        ║${NC}"
    echo -e "${CYAN}╚════════════════════════════════════════╝${NC}"

    if [ "$QUICK_MODE" = true ]; then
        print_warning "Running in QUICK mode"
    fi

    echo ""
    print_info "Starting validation at $(date '+%Y-%m-%d %H:%M:%S')"

    # Run all checks (continue even if some fail)
    run_docker_check || true
    run_code_validation || true
    run_tests || true

    local end_time=$(date +%s)
    local duration=$((end_time - start_time))

    # Final summary
    print_header "Validation Summary"

    echo ""
    print_info "Validation completed in ${duration}s"
    echo ""

    if [ ${#FAILED_CHECKS[@]} -eq 0 ]; then
        echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
        echo -e "${GREEN}║                                        ║${NC}"
        echo -e "${GREEN}║   ✓ ALL VALIDATIONS PASSED!           ║${NC}"
        echo -e "${GREEN}║                                        ║${NC}"
        echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
        echo ""
        print_success "System is healthy and code quality is good"
        echo ""
        print_info "You can safely commit your changes"
        exit 0
    else
        echo -e "${RED}╔════════════════════════════════════════╗${NC}"
        echo -e "${RED}║                                        ║${NC}"
        echo -e "${RED}║   ✗ SOME VALIDATIONS FAILED           ║${NC}"
        echo -e "${RED}║                                        ║${NC}"
        echo -e "${RED}╚════════════════════════════════════════╝${NC}"
        echo ""
        print_error "Failed checks:"
        for check in "${FAILED_CHECKS[@]}"; do
            echo "  • $check"
        done
        echo ""
        print_info "Please fix the issues before committing"
        exit 1
    fi
}

# Run main
main
