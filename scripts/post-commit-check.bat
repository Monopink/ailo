@echo off
REM Post-commit code quality check for Windows
REM Run this after committing large changesets to verify code quality

echo ==========================================
echo Post-Commit Code Quality Check
echo ==========================================
echo.

cd /d "%~dp0\.."

echo 1. Running mypy type checker...
echo ------------------------------------------
mypy backend/app --config-file=pyproject.toml --no-error-summary --explicit-package-bases
if errorlevel 1 (
    echo WARNING: mypy found type errors ^(expected for this codebase^)
    echo.
)

echo.
echo 2. Running pylint code quality checker...
echo ------------------------------------------
pylint backend/app --rcfile=pyproject.toml --score=yes
if errorlevel 1 (
    echo WARNING: pylint found issues
    echo.
)

echo.
echo 3. Running import-linter architecture check...
echo ------------------------------------------
python scripts/run_import_linter.py
if errorlevel 1 (
    echo ERROR: import-linter found architecture violations!
    exit /b 1
)

echo.
echo ==========================================
echo Post-commit checks completed
echo ==========================================
