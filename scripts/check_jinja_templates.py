#!/usr/bin/env python3
"""Validate Jinja template syntax for admin HTML templates."""

from __future__ import annotations

import argparse
from pathlib import Path

from jinja2 import Environment, select_autoescape
from jinja2.exceptions import TemplateSyntaxError

DEFAULT_GLOB = "backend/app/admin/templates/**/*.html"


def collect_template_files(paths: list[str]) -> list[Path]:
    """Collect template files from CLI args or default glob."""
    if paths:
        return [Path(item) for item in paths if item.endswith(".html")]
    return sorted(Path().glob(DEFAULT_GLOB))


def validate_templates(files: list[Path]) -> int:
    """Parse templates and return process exit code."""
    if not files:
        print("No template files to validate.")
        return 0

    env = Environment(autoescape=select_autoescape(enabled_extensions=("html", "xml")))
    errors: list[str] = []
    for file_path in files:
        if not file_path.exists():
            continue
        try:
            source = file_path.read_text(encoding="utf-8")
            env.parse(source)
        except TemplateSyntaxError as exc:
            line = exc.lineno or 1
            errors.append(f"{file_path}:{line} {exc.message}")
        except UnicodeDecodeError as exc:
            errors.append(f"{file_path}:1 Failed to read as UTF-8 ({exc})")

    if errors:
        print("Jinja template validation failed:")
        for item in errors:
            print(f"  - {item}")
        return 1

    print(f"Jinja template validation passed ({len(files)} files).")
    return 0


def main() -> int:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description="Check Jinja template syntax.")
    parser.add_argument(
        "paths",
        nargs="*",
        help="Optional template file paths. Defaults to all admin templates.",
    )
    args = parser.parse_args()
    files = collect_template_files(args.paths)
    return validate_templates(files)


if __name__ == "__main__":
    raise SystemExit(main())
