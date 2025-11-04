#!/usr/bin/env python3
"""
Database migration management script for host machine.

This script provides convenient commands for managing database migrations
using Alembic from the host machine, connecting to Docker PostgreSQL.
"""

import os
import sys
import subprocess
from pathlib import Path


def load_env_file():
    """Load environment variables from .env.migration file."""
    env_file = Path(__file__).parent / ".env.migration"
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    # Remove quotes if present
                    value = value.strip("\"'")
                    os.environ[key] = value
        print(f"Loaded environment variables from {env_file}")
    else:
        print("Warning: .env.migration file not found")


def run_command(cmd, cwd=None):
    """Run a shell command and return the result."""
    if cwd is None:
        cwd = Path(__file__).parent

    print(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)

    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)

    return result.returncode == 0


def main():
    """Main entry point for the migration script."""
    # Load environment variables
    load_env_file()

    if len(sys.argv) < 2:
        print("Usage: python migrate.py <command> [args...]")
        print("\nAvailable commands:")
        print("  current     - Show current migration version")
        print("  history     - Show migration history")
        print("  upgrade     - Apply pending migrations")
        print("  downgrade   - Downgrade to previous migration")
        print("  revision    - Create a new migration")
        print("  autogenerate - Auto-generate migration from model changes")
        print("  check       - Check if migrations are up to date")
        print("  init        - Initialize migration system (first time setup)")
        return

    command = sys.argv[1]
    args = sys.argv[2:] if len(sys.argv) > 2 else []

    # Change to backend directory
    backend_dir = Path(__file__).parent

    if command == "current":
        run_command("alembic current", backend_dir)

    elif command == "history":
        run_command("alembic history --verbose", backend_dir)

    elif command == "upgrade":
        target = args[0] if args else "head"
        run_command(f"alembic upgrade {target}", backend_dir)

    elif command == "downgrade":
        target = args[0] if args else "-1"
        run_command(f"alembic downgrade {target}", backend_dir)

    elif command == "revision":
        if not args:
            print("Error: revision command requires a message")
            print("Usage: python migrate.py revision 'Your migration message'")
            return
        message = " ".join(args)
        run_command(f'alembic revision -m "{message}"', backend_dir)

    elif command == "autogenerate":
        if not args:
            print("Error: autogenerate command requires a message")
            print("Usage: python migrate.py autogenerate 'Your migration message'")
            return
        message = " ".join(args)
        run_command(f'alembic revision --autogenerate -m "{message}"', backend_dir)

    elif command == "check":
        run_command("alembic check", backend_dir)

    elif command == "stamp":
        if not args:
            print("Error: stamp command requires a revision id (e.g., heads or <rev>)")
            print("Usage: python migrate.py stamp <revision>")
            return
        target = args[0]
        run_command(f"alembic stamp {target}", backend_dir)

    elif command == "init":
        print("Generating initial migration and marking database as current...")
        if run_command('alembic revision --autogenerate -m "Initial database schema"', backend_dir):
            run_command("alembic stamp head", backend_dir)
            print("Migration system initialized successfully!")

    else:
        print(f"Unknown command: {command}")
        print("Run 'python migrate.py' for usage information")


if __name__ == "__main__":
    main()
