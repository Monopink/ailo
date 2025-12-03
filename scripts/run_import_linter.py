#!/usr/bin/env python3
"""Wrapper script for import-linter to handle Windows encoding issues."""

import os
import sys
import subprocess


def main() -> int:
    """Run import-linter with proper encoding settings for Windows."""
    # Set UTF-8 encoding for Windows
    if sys.platform == "win32":
        os.environ["PYTHONIOENCODING"] = "utf-8"
        # Try to set console to UTF-8 mode
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleCP(65001)
            kernel32.SetConsoleOutputCP(65001)
        except Exception:
            pass  # Ignore if setting console encoding fails

        # Reconfigure stdout/stderr to use UTF-8 encoding
        # This is the key fix: ensure Python's print() uses UTF-8, not GBK
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

    # Get directories
    project_root = os.path.dirname(os.path.dirname(__file__))
    backend_dir = os.path.join(project_root, "backend")
    app_dir = os.path.join(backend_dir, "app")
    config_path = os.path.join(project_root, ".importlinter")

    # Set PYTHONPATH to backend (same as Dockerfile: ENV PYTHONPATH=/backend)
    # This allows imports like "from app.core.database" to work
    env = os.environ.copy()
    env["PYTHONPATH"] = backend_dir

    # Disable rich library colors and Unicode decorations
    # This prevents Unicode encoding issues on Windows console
    env["NO_COLOR"] = "1"

    # Find lint-imports executable
    # It should be in the Scripts directory of the Python installation
    import site

    # Try user site-packages Scripts directory first
    user_scripts = os.path.join(site.USER_BASE, "Python312", "Scripts")
    lint_imports_exe = os.path.join(user_scripts, "lint-imports.exe")

    if not os.path.exists(lint_imports_exe):
        # Try system Python Scripts directory
        scripts_dir = os.path.join(sys.prefix, "Scripts")
        lint_imports_exe = os.path.join(scripts_dir, "lint-imports.exe")

    if not os.path.exists(lint_imports_exe):
        print("Error: lint-imports.exe not found", file=sys.stderr)
        print(f"Searched in: {user_scripts} and {scripts_dir}", file=sys.stderr)
        return 1

    # Run lint-imports from backend directory
    # Config expects root_package = app, which is at backend/app
    try:
        # With NO_COLOR=1, rich outputs plain text without Unicode decorations
        result = subprocess.run(
            [lint_imports_exe, "--config", config_path],
            cwd=backend_dir,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        # Print output directly (no Unicode decorations with NO_COLOR=1)
        if result.stdout:
            print(result.stdout, end="")

        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)

        return result.returncode
    except Exception as e:
        print(f"Error running import-linter: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
