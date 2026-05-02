"""Attack signature detection utilities for API security enforcement."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.enums import SeverityLevel, ViolationType

_MAX_FIELD_VALUE_LENGTH = 2048

_SQL_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?:'|\")\s*(?:or|and)\s*\d+\s*=\s*\d+", re.IGNORECASE),
    re.compile(r"\bunion\b\s+\bselect\b", re.IGNORECASE),
    re.compile(r"\bselect\b\s*\*\s*\bfrom\b", re.IGNORECASE),
    re.compile(r"\bsleep\s*\(", re.IGNORECASE),
    re.compile(r"\bbenchmark\s*\(", re.IGNORECASE),
    re.compile(r"--|/\*|\*/|#", re.IGNORECASE),
)

_COMMAND_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"(?:;|&&|\|\|)\s*(?:cat|bash|sh|curl|wget|python|perl|powershell|cmd)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\$\([^\)]{1,128}\)"),
    re.compile(r"`[^`]{1,128}`"),
)

_PATH_TRAVERSAL_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\.\./|\.\.\\"),
    re.compile(r"%2e%2e%2f|%2e%2e/|%2e%2e%5c", re.IGNORECASE),
    re.compile(r"/(?:etc/passwd|proc/self|windows/win\.ini)", re.IGNORECASE),
)


@dataclass(slots=True, frozen=True)
class AttackMatch:
    """Attack match result for one request-level scan."""

    violation_type: ViolationType
    severity_level: SeverityLevel
    rule_code: str
    field_name: str
    evidence: str


def _normalize_value(raw_value: str) -> str:
    """Normalize a potentially untrusted field value for pattern matching."""
    return raw_value.strip()[:_MAX_FIELD_VALUE_LENGTH]


def detect_attack_match(field_name: str, raw_value: str) -> AttackMatch | None:
    """Detect whether a single field contains attack signatures."""
    value = _normalize_value(raw_value)
    if not value:
        return None

    for pattern in _SQL_PATTERNS:
        if pattern.search(value):
            return AttackMatch(
                violation_type=ViolationType.SQL_INJECTION,
                severity_level=SeverityLevel.HIGH,
                rule_code="sql_injection_pattern",
                field_name=field_name,
                evidence=value,
            )

    for pattern in _COMMAND_PATTERNS:
        if pattern.search(value):
            return AttackMatch(
                violation_type=ViolationType.COMMAND_INJECTION,
                severity_level=SeverityLevel.HIGH,
                rule_code="command_injection_pattern",
                field_name=field_name,
                evidence=value,
            )

    for pattern in _PATH_TRAVERSAL_PATTERNS:
        if pattern.search(value):
            return AttackMatch(
                violation_type=ViolationType.PATH_TRAVERSAL,
                severity_level=SeverityLevel.HIGH,
                rule_code="path_traversal_pattern",
                field_name=field_name,
                evidence=value,
            )

    return None


def detect_attack_in_fields(fields: dict[str, str]) -> AttackMatch | None:
    """Scan multiple fields and return the first detected attack match."""
    for field_name, raw_value in fields.items():
        match = detect_attack_match(field_name, raw_value)
        if match is not None:
            return match
    return None
