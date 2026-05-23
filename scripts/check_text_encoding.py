#!/usr/bin/env python3
"""Validate text files encoding and flag common garbled text patterns."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

UTF8_BOM = b"\xef\xbb\xbf"

# Conservative mojibake markers for UTF-8 interpreted as Latin-1/Windows-1252.
MOJIBAKE_TOKEN_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"Ã[\x80-\xBF]"),
    re.compile(r"Â[\x80-\xBF ]"),
    re.compile(r"â€[˜™œš›“”]"),
    re.compile(r"ðŸ[\x80-\xBF]"),
    re.compile("\u00ef\u00bb\u00bf"),
    re.compile("\u951f\u65a4\u62f7"),
)

# C1 controls (U+0080-U+009F) usually indicate decoding mistakes in text files.
C1_CONTROL_PATTERN = re.compile(r"[\u0080-\u009F]")


@dataclass(slots=True)
class EncodingIssue:
    """Single encoding validation issue."""

    path: Path
    message: str


def is_probably_binary(data: bytes) -> bool:
    """Treat files containing NUL bytes as binary and skip them."""
    return b"\x00" in data


def detect_mojibake_tokens(text: str) -> str | None:
    """Return a short reason when conservative mojibake patterns are found."""
    for pattern in MOJIBAKE_TOKEN_PATTERNS:
        if pattern.search(text):
            escaped_pattern = pattern.pattern.encode("unicode_escape").decode("ascii")
            return f"matched suspicious pattern `{escaped_pattern}`"
    if C1_CONTROL_PATTERN.search(text):
        return "contains C1 control characters (U+0080-U+009F)"
    return None


def safe_print(line: str) -> None:
    """Print text safely even when terminal encoding cannot represent characters."""
    try:
        print(line)
    except UnicodeEncodeError:
        encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
        fallback = line.encode(encoding, errors="backslashreplace").decode(encoding)
        print(fallback)


def configure_output_streams() -> None:
    """Use non-strict output error handling for mixed terminal encodings."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(errors="backslashreplace")
        except ValueError:
            continue


def validate_file(path: Path, *, check_mojibake: bool) -> list[EncodingIssue]:
    """Validate a single file and return discovered issues."""
    issues: list[EncodingIssue] = []
    if not path.exists():
        return issues
    if path.is_dir():
        return issues

    try:
        raw = path.read_bytes()
    except OSError as exc:
        return [EncodingIssue(path=path, message=f"unable to read file ({exc})")]

    if is_probably_binary(raw):
        return issues

    if raw.startswith(UTF8_BOM):
        issues.append(EncodingIssue(path=path, message="contains UTF-8 BOM"))

    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        issues.append(
            EncodingIssue(
                path=path,
                message=(
                    "is not valid UTF-8 "
                    f"(byte {exc.start}-{exc.end}, reason: {exc.reason})"
                ),
            )
        )
        return issues

    if "\ufffd" in text:
        issues.append(
            EncodingIssue(
                path=path,
                message="contains replacement character U+FFFD (possible garbled text)",
            )
        )

    if check_mojibake:
        reason = detect_mojibake_tokens(text)
        if reason:
            issues.append(
                EncodingIssue(
                    path=path,
                    message=f"possible mojibake detected ({reason})",
                )
            )
    return issues


def collect_paths(raw_paths: Iterable[str]) -> list[Path]:
    """Keep only existing file paths from hook inputs."""
    paths: list[Path] = []
    for raw_path in raw_paths:
        path = Path(raw_path)
        if path.exists() and path.is_file():
            paths.append(path)
    return paths


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for pre-commit integration."""
    configure_output_streams()
    parser = argparse.ArgumentParser(
        description="Check text files are valid UTF-8 and free from common garbling markers."
    )
    parser.add_argument(
        "--no-mojibake-check",
        action="store_true",
        help="Skip conservative mojibake pattern detection.",
    )
    parser.add_argument("paths", nargs="*", help="Files passed by pre-commit.")
    args = parser.parse_args(argv)

    files = collect_paths(args.paths)
    if not files:
        return 0

    all_issues: list[EncodingIssue] = []
    for file_path in files:
        all_issues.extend(
            validate_file(file_path, check_mojibake=not args.no_mojibake_check)
        )

    if not all_issues:
        safe_print(f"Encoding check passed ({len(files)} files).")
        return 0

    safe_print("Encoding check failed:")
    for issue in all_issues:
        safe_print(f"  - {issue.path}: {issue.message}")
    safe_print(
        "Hint: save files as UTF-8 (without BOM) and fix garbled text before committing."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
