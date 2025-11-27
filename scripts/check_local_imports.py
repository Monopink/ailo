#!/usr/bin/env python3
"""Guard against runtime imports that are nested inside functions."""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path
from typing import List, Sequence, Tuple

DEFAULT_SCAN_PATHS: tuple[Path, ...] = (
    Path("backend/app/admin/views"),
    Path("backend/app/api"),
    Path("backend/app/crud"),
    Path("backend/app/services/message"),
)


class LocalImportVisitor(ast.NodeVisitor):
    """Track import nodes that do not live at the module scope."""

    def __init__(self) -> None:
        self.stack: List[ast.AST] = []
        self.issues: List[int] = []

    def visit(self, node: ast.AST) -> None:
        self.stack.append(node)
        super().visit(node)
        self.stack.pop()

    def visit_Import(self, node: ast.Import) -> None:
        if self._should_report():
            self.issues.append(node.lineno)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if self._should_report():
            self.issues.append(node.lineno)
        self.generic_visit(node)

    def _should_report(self) -> bool:
        if len(self.stack) < 2:
            return False
        parent = self.stack[-2]
        if isinstance(parent, ast.Module):
            return False
        if self._is_nested_in_type_checking():
            return False
        return True

    def _is_nested_in_type_checking(self) -> bool:
        for ancestor in self.stack[:-1]:
            if isinstance(ancestor, ast.If) and self._contains_type_checking(ancestor.test):
                return True
        return False

    @staticmethod
    def _contains_type_checking(node: ast.AST | None) -> bool:
        if node is None:
            return False
        for child in ast.walk(node):
            if isinstance(child, ast.Name) and child.id == "TYPE_CHECKING":
                return True
            if isinstance(child, ast.Attribute) and child.attr == "TYPE_CHECKING":
                return True
        return False


def collect_target_files(paths: Sequence[str]) -> list[Path]:
    """Expand the command line targets to a deduplicated list of Python files."""
    resolved: list[Path] = []
    seen: set[Path] = set()
    for candidate in paths:
        path = Path(candidate)
        if not path.exists():
            continue
        if path.is_file():
            resolved_path = path.resolve()
            if resolved_path not in seen:
                seen.add(resolved_path)
                resolved.append(resolved_path)
            continue
        for file_path in sorted(path.rglob("*.py")):
            if "__pycache__" in file_path.parts:
                continue
            resolved_path = file_path.resolve()
            if resolved_path in seen:
                continue
            seen.add(resolved_path)
            resolved.append(resolved_path)
    return resolved


def analyze_file(path: Path) -> List[Tuple[int, str]]:
    """Return the line numbers and snippets of nested imports in `path`."""
    try:
        source = path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise SystemExit(f"Unable to read {path}: {exc}") from exc

    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        raise SystemExit(f"Failed to parse {path}: {exc}") from exc

    visitor = LocalImportVisitor()
    visitor.visit(tree)
    if not visitor.issues:
        return []
    lines = source.splitlines()
    return [
        (lineno, lines[lineno - 1].strip()) for lineno in visitor.issues if 0 <= lineno - 1 < len(lines)
    ]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Detect nested python imports outside TYPE_CHECKING blocks."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="Files or directories to scan. Defaults to the core backend app.",
    )
    args = parser.parse_args(argv)

    targets = args.paths if args.paths else [str(path) for path in DEFAULT_SCAN_PATHS]
    files = collect_target_files(targets)
    if not files:
        return 0

    findings: list[Tuple[Path, List[Tuple[int, str]]]] = []
    for file_path in files:
        issues = analyze_file(file_path)
        if issues:
            findings.append((file_path, issues))

    if not findings:
        return 0

    for path, issues in findings:
        print(f"\n{path}:")
        for line_no, snippet in issues:
            print(f"  {line_no}: {snippet}")

    print("\nFound nested imports in the files above. Move them to the module scope or guard them with TYPE_CHECKING.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
