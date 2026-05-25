"""Attack signature detection utilities for API security enforcement."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from app.enums import SeverityLevel, ViolationType

_MAX_FIELD_VALUE_LENGTH = 2048
FieldType = Literal["free_text", "identifier", "opaque_token"]

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


@dataclass(slots=True, frozen=True)
class AttackScanField:
    """Field with semantic type for attack scan policy."""

    field_name: str
    raw_value: str
    field_type: FieldType = "free_text"


def _normalize_value(raw_value: str) -> str:
    """Normalize a potentially untrusted field value for pattern matching."""
    return raw_value.strip()[:_MAX_FIELD_VALUE_LENGTH]


def detect_attack_match(
    field_name: str,
    raw_value: str,
    *,
    field_type: FieldType = "free_text",
) -> AttackMatch | None:
    """Detect whether a single field contains attack signatures."""
    if field_type == "opaque_token":
        return None

    value = _normalize_value(raw_value)
    if not value:
        return None

    if field_type == "free_text":
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


def _normalize_fields(
    fields: Mapping[str, str] | Sequence[AttackScanField],
) -> list[AttackScanField]:
    if isinstance(fields, Mapping):
        return [
            AttackScanField(field_name=field_name, raw_value=raw_value, field_type="free_text")
            for field_name, raw_value in fields.items()
        ]
    return list(fields)


def detect_attack_in_fields(
    fields: Mapping[str, str] | Sequence[AttackScanField],
) -> AttackMatch | None:
    """Scan multiple fields and return the first detected attack match."""
    for field in _normalize_fields(fields):
        match = detect_attack_match(
            field.field_name,
            field.raw_value,
            field_type=field.field_type,
        )
        if match is not None:
            return match
    return None
