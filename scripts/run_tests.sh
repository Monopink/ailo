#!/bin/bash
# ============================================================================
# Test Runner Script
# ============================================================================
# This script runs the test suite for the backend application.
# Usage:
#   ./scripts/run_tests.sh              # Run all tests
#   ./scripts/run_tests.sh --fast       # Run fast tests only (exclude slow)
#   ./scripts/run_tests.sh --coverage   # Run with coverage report
#   ./scripts/run_tests.sh --verbose    # Run with verbose output
# ============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
TEST_DIR="backend/tests"
PYTEST_ARGS="-v"
RUN_COVERAGE=false
FAST_MODE=false

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

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --fast)
            FAST_MODE=true
            PYTEST_ARGS="$PYTEST_ARGS -m 'not slow'"
            shift
            ;;
        --coverage)
            RUN_COVERAGE=true
            shift
            ;;
        --verbose)
            PYTEST_ARGS="$PYTEST_ARGS -vv"
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --fast       Run fast tests only (exclude slow tests)"
            echo "  --coverage   Generate coverage report"
            echo "  --verbose    Run with verbose output"
            echo "  --help       Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                # Run all tests"
            echo "  $0 --fast         # Run fast tests only"
            echo "  $0 --coverage     # Run with coverage"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Check if pytest is installed
check_pytest() {
    print_header "Checking Test Environment"

    if ! command -v pytest &> /dev/null; then
        print_error "pytest is not installed"
        echo ""
        print_info "Install pytest: pip install pytest pytest-asyncio httpx"
        exit 1
    fi

    print_success "pytest is installed"

    if [ "$RUN_COVERAGE" = true ]; then
        if ! command -v coverage &> /dev/null; then
            print_error "coverage is not installed"
            echo ""
            print_info "Install coverage: pip install pytest-cov"
            exit 1
        fi
        print_success "coverage is installed"
    fi
}

# Check if test directory exists
check_test_directory() {
    if [ ! -d "$TEST_DIR" ]; then
        print_error "Test directory not found: $TEST_DIR"
        exit 1
    fi

    local test_count=$(find "$TEST_DIR" -name "test_*.py" | wc -l)
    print_info "Found $test_count test files"
}

# Run tests
run_tests() {
    print_header "Running Tests"

    if [ "$FAST_MODE" = true ]; then
        print_info "Running in FAST mode (excluding slow tests)"
    fi

    if [ "$RUN_COVERAGE" = true ]; then
        print_info "Running with coverage report"
        PYTEST_ARGS="$PYTEST_ARGS --cov=backend/app --cov-report=term-missing --cov-report=html"
    fi

    echo ""
    echo "Command: pytest $TEST_DIR $PYTEST_ARGS"
    echo ""

    if pytest $TEST_DIR $PYTEST_ARGS; then
        return 0
    else
        return 1
    fi
}

# Main execution
main() {
    echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║   Test Runner Script                  ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"

    check_pytest
    check_test_directory

    if run_tests; then
        print_header "Test Summary"
        echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
        echo -e "${GREEN}║   ✓ ALL TESTS PASSED!                 ║${NC}"
        echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"

        if [ "$RUN_COVERAGE" = true ]; then
            echo ""
            print_info "Coverage report generated in htmlcov/index.html"
        fi

        exit 0
    else
        print_header "Test Summary"
        echo -e "${RED}╔════════════════════════════════════════╗${NC}"
        echo -e "${RED}║   ✗ SOME TESTS FAILED                 ║${NC}"
        echo -e "${RED}╚════════════════════════════════════════╝${NC}"
        exit 1
    fi
}

# Run main
main
