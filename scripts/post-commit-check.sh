#!/bin/bash
# Post-commit code quality check
# Run this after committing large changesets to verify code quality

set -e

echo "=========================================="
echo "Post-Commit Code Quality Check"
echo "=========================================="
echo ""

# Get the project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "1. Running mypy type checker..."
echo "------------------------------------------"
mypy backend/app --config-file=pyproject.toml --no-error-summary --explicit-package-bases || {
    echo "⚠️  mypy found type errors (expected for this codebase)"
    echo ""
}

echo ""
echo "2. Running pylint code quality checker..."
echo "------------------------------------------"
pylint backend/app --rcfile=pyproject.toml --score=yes || {
    echo "⚠️  pylint found issues"
    echo ""
}

echo ""
echo "3. Running import-linter architecture check..."
echo "------------------------------------------"
python scripts/run_import_linter.py || {
    echo "❌ import-linter found architecture violations!"
    exit 1
}

echo ""
echo "=========================================="
echo "✅ Post-commit checks completed"
echo "=========================================="
