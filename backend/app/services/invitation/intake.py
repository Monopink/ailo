"""Invitation intake parsing helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass

from fastapi import HTTPException, status

INVITE_CODE_LENGTH = 6
INVITE_TOKEN_PATTERN = re.compile(r"(?<![A-Za-z0-9])([A-Za-z0-9]{6})(?![A-Za-z0-9])")
TRIGGER_PATTERN = re.compile(r"^[a-z0-9_\\-]{1,32}$")
INVITE_EVENT_SOURCES = frozenset(
    {
        "login",
        "setup",
        "link",
        "invite_bind_page",
        "invite_share_page",
    }
)


@dataclass(frozen=True)
class InviteIntakeCandidate:
    """Resolved intake candidate from raw input."""

    first_candidate: str | None
    normalized_code: str | None


def normalize_invite_code_or_none(raw: str | None) -> str | None:
    """Normalize invite code and return None when format is invalid."""
    if raw is None:
        return None
    candidate = raw.strip().upper()
    if candidate == "":
        return None
    if len(candidate) != INVITE_CODE_LENGTH:
        return None
    if not (candidate.isascii() and candidate.isalnum()):
        return None
    return candidate


def normalize_invite_code_or_raise(raw: str) -> str:
    """Normalize invite code and raise request error when format is invalid."""
    normalized = normalize_invite_code_or_none(raw)
    if normalized is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请求参数错误")
    return normalized


def extract_first_candidate_from_text(raw_text: str | None) -> str | None:
    """Extract first standalone 6-char alnum token from raw text."""
    if raw_text is None:
        return None
    normalized_text = raw_text.strip().upper()
    if normalized_text == "":
        return None
    match = INVITE_TOKEN_PATTERN.search(normalized_text)
    if match is None:
        return None
    return match.group(1)


def resolve_intake_candidate(
    *,
    raw_text: str | None,
    invite_code: str | None,
) -> InviteIntakeCandidate:
    """Resolve first candidate and normalized code for intake flow."""
    normalized_from_param = normalize_invite_code_or_none(invite_code)
    if normalized_from_param is not None:
        return InviteIntakeCandidate(
            first_candidate=normalized_from_param,
            normalized_code=normalized_from_param,
        )

    candidate_from_text = extract_first_candidate_from_text(raw_text)
    normalized_from_text = normalize_invite_code_or_none(candidate_from_text)
    return InviteIntakeCandidate(
        first_candidate=candidate_from_text,
        normalized_code=normalized_from_text,
    )


def normalize_trigger_or_raise(raw: str) -> str:
    """Normalize trigger and raise request error when invalid."""
    candidate = raw.strip().lower()
    if TRIGGER_PATTERN.fullmatch(candidate) is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请求参数错误")
    return candidate


def normalize_event_source_or_raise(raw: str) -> str:
    """Normalize event source and raise request error when unsupported."""
    candidate = raw.strip().lower()
    if candidate not in INVITE_EVENT_SOURCES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请求参数错误")
    return candidate
