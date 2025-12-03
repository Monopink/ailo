#!/bin/bash
# ============================================================================
# Code Quality Validation Script
# ============================================================================
# This script runs all code quality checks on the backend Python code.
# Usage:
#   ./scripts/validate.sh          # Check all files
#   ./scripts/validate.sh --quick  # Check only git-modified files
#   ./scripts/validate.sh --help   # Show help
# ============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
BACKEND_DIR="backend/app"
SCRIPTS_DIR="scripts"
CHECK_MODE="all"
FAILED_CHECKS=()

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --quick)
            CHECK_MODE="quick"
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --quick    Only check git-modified files"
            echo "  --help     Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                # Check all files"
            echo "  $0 --quick        # Check only modified files"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

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

# Get files to check
get_files_to_check() {
    if [ "$CHECK_MODE" = "quick" ]; then
        # Get git-modified Python files
        git diff --name-only --diff-filter=ACMR HEAD | grep "^${BACKEND_DIR}/.*\.py$" || true
    else
        # Get all Python files
        find "$BACKEND_DIR" -name "*.py" -not -path "*/migrations/*" -not -path "*/__pycache__/*"
    fi
}

# Check if tools are installed
check_tools() {
    print_header "Checking Required Tools"

    local tools=("python" "ruff" "mypy" "lint-imports")
    local missing_tools=()

    for tool in "${tools[@]}"; do
        if command -v "$tool" &> /dev/null; then
            print_success "$tool is installed"
        else
            print_error "$tool is NOT installed"
            missing_tools+=("$tool")
        fi
    done

    if [ ${#missing_tools[@]} -ne 0 ]; then
        print_error "Missing tools: ${missing_tools[*]}"
        echo "Please install missing tools: pip install -r backend/app/requirements.txt"
        exit 1
    fi
}

# Run syntax check
check_syntax() {
    print_header "1. Syntax Check"

    local files=$(get_files_to_check)
    if [ -z "$files" ]; then
        print_warning "No Python files to check"
        return 0
    fi

    local failed=0
    while IFS= read -r file; do
        if python -m py_compile "$file" 2>/dev/null; then
            echo "  ✓ $file"
        else
            print_error "Syntax error in $file"
            python -m py_compile "$file"
            failed=1
        fi
    done <<< "$files"

    if [ $failed -eq 0 ]; then
        print_success "All files have valid syntax"
    else
        FAILED_CHECKS+=("Syntax Check")
        return 1
    fi
}

# Run import location check
check_import_locations() {
    print_header "2. Import Location Check"

    if python "$SCRIPTS_DIR/check_local_imports.py" $BACKEND_DIR; then
        print_success "All imports are at module level"
    else
        print_error "Found imports inside functions"
        FAILED_CHECKS+=("Import Location Check")
        return 1
    fi
}

# Run Ruff format check (replaces black + isort)
check_ruff_format() {
    print_header "3. Code Formatting (Ruff)"

    if [ "$CHECK_MODE" = "quick" ]; then
        local files=$(get_files_to_check)
        if [ -z "$files" ]; then
            print_warning "No Python files to check"
            return 0
        fi
        if echo "$files" | xargs ruff format --check 2>/dev/null; then
            print_success "Code formatting is correct"
        else
            print_error "Code formatting issues found"
            echo "Run: ruff format backend/app"
            FAILED_CHECKS+=("Ruff Format")
            return 1
        fi
    else
        if ruff format --check "$BACKEND_DIR" 2>/dev/null; then
            print_success "Code formatting is correct"
        else
            print_error "Code formatting issues found"
            echo "Run: ruff format $BACKEND_DIR"
            FAILED_CHECKS+=("Ruff Format")
            return 1
        fi
    fi
}

# Run Ruff lint check (replaces pylint)
check_ruff_lint() {
    print_header "4. Code Quality (Ruff)"

    if [ "$CHECK_MODE" = "quick" ]; then
        local files=$(get_files_to_check)
        if [ -z "$files" ]; then
            print_warning "No Python files to check"
            return 0
        fi
        if echo "$files" | xargs ruff check 2>/dev/null; then
            print_success "Code quality check passed"
        else
            print_error "Code quality issues found"
            echo "Run: ruff check --fix backend/app"
            FAILED_CHECKS+=("Ruff Lint")
            return 1
        fi
    else
        if ruff check "$BACKEND_DIR" 2>/dev/null; then
            print_success "Code quality check passed"
        else
            print_error "Code quality issues found"
            echo "Run: ruff check --fix $BACKEND_DIR"
            FAILED_CHECKS+=("Ruff Lint")
            return 1
        fi
    fi
}

# Run mypy type check
check_mypy() {
    print_header "5. Type Checking (mypy)"

    if [ "$CHECK_MODE" = "quick" ]; then
        local files=$(get_files_to_check)
        if [ -z "$files" ]; then
            print_warning "No Python files to check"
            return 0
        fi
        if echo "$files" | xargs mypy --config-file pyproject.toml 2>/dev/null; then
            print_success "Type checking passed"
        else
            print_error "Type checking failed"
            FAILED_CHECKS+=("mypy Type Check")
            return 1
        fi
    else
        if mypy --config-file pyproject.toml "$BACKEND_DIR" 2>/dev/null; then
            print_success "Type checking passed"
        else
            print_error "Type checking failed"
            FAILED_CHECKS+=("mypy Type Check")
            return 1
        fi
    fi
}

# Run import-linter
check_import_linter() {
    print_header "6. Architecture Contracts (import-linter)"

    # Use the wrapper script which sets correct PYTHONPATH
    if python scripts/run_import_linter.py; then
        print_success "Architecture contracts satisfied"
    else
        print_error "Architecture contract violations found"
        FAILED_CHECKS+=("import-linter")
        return 1
    fi
}

# Main execution
main() {
    echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║   Code Quality Validation (Ruff)      ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"

    if [ "$CHECK_MODE" = "quick" ]; then
        print_warning "Running in QUICK mode (git-modified files only)"
    else
        echo "Running in FULL mode (all files)"
    fi

    # Check tools
    check_tools

    # Run all checks (continue even if some fail)
    check_syntax || true
    check_import_locations || true
    check_ruff_format || true
    check_ruff_lint || true
    check_mypy || true
    check_import_linter || true

    # Summary
    print_header "Validation Summary"

    if [ ${#FAILED_CHECKS[@]} -eq 0 ]; then
        echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
        echo -e "${GREEN}║   ✓ ALL CHECKS PASSED!                ║${NC}"
        echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
        exit 0
    else
        echo -e "${RED}╔════════════════════════════════════════╗${NC}"
        echo -e "${RED}║   ✗ SOME CHECKS FAILED                ║${NC}"
        echo -e "${RED}╚════════════════════════════════════════╝${NC}"
        echo ""
        print_error "Failed checks:"
        for check in "${FAILED_CHECKS[@]}"; do
            echo "  - $check"
        done
        exit 1
    fi
}

# Run main
main
