"""In-process temporary token store for persona batch-edit imports."""

from __future__ import annotations

import asyncio
import secrets
import time
from dataclasses import dataclass
from typing import Any

_IMPORT_TOKEN_TTL_SECONDS = 900
_IMPORT_MAX_SELECTION = 500
_memory_store: dict[str, tuple[dict[str, Any], int]] = {}
_memory_lock = asyncio.Lock()


@dataclass
class PersonaBatchImportSelection:
    """Stored selection payload for batch-edit import."""

    admin_id: int
    persona_ids: list[int]
    created_at_ms: int
    expires_at_ms: int


class PersonaBatchImportStoreError(RuntimeError):
    """Base error for persona batch import token operations."""


class PersonaBatchImportSelectionLimitError(PersonaBatchImportStoreError):
    """Raised when selected persona count exceeds max limit."""


class PersonaBatchImportTokenNotFoundError(PersonaBatchImportStoreError):
    """Raised when import token does not exist or already consumed."""


class PersonaBatchImportTokenForbiddenError(PersonaBatchImportStoreError):
    """Raised when token owner does not match current admin."""


def _now_ms() -> int:
    return int(time.time() * 1000)


def _normalize_persona_ids(persona_ids: list[int]) -> list[int]:
    normalized: list[int] = []
    seen: set[int] = set()
    for raw_id in persona_ids:
        try:
            value = int(raw_id)
        except (TypeError, ValueError):
            continue
        if value <= 0 or value in seen:
            continue
        seen.add(value)
        normalized.append(value)
    return normalized


async def _cleanup_memory_store(now_ms: int) -> None:
    expired_tokens = [
        token
        for token, (_payload, expires_at_ms) in _memory_store.items()
        if expires_at_ms <= now_ms
    ]
    for token in expired_tokens:
        _memory_store.pop(token, None)


async def create_persona_batch_import_token(
    *,
    admin_id: int,
    persona_ids: list[int],
) -> str:
    """Create a short-lived token for selected personas."""
    ttl_seconds = _IMPORT_TOKEN_TTL_SECONDS
    max_selection = _IMPORT_MAX_SELECTION

    normalized_ids = _normalize_persona_ids(persona_ids)
    if len(normalized_ids) == 0:
        raise PersonaBatchImportStoreError("No valid persona selected")
    if len(normalized_ids) > max_selection:
        raise PersonaBatchImportSelectionLimitError(
            f"Maximum selectable personas is {max_selection}"
        )

    now_ms = _now_ms()
    expires_at_ms = now_ms + ttl_seconds * 1000
    token = secrets.token_urlsafe(24)
    payload = {
        "admin_id": admin_id,
        "persona_ids": normalized_ids,
        "created_at_ms": now_ms,
        "expires_at_ms": expires_at_ms,
    }

    async with _memory_lock:
        await _cleanup_memory_store(now_ms)
        _memory_store[token] = (payload, expires_at_ms)
    return token


async def consume_persona_batch_import_token(
    *,
    admin_id: int,
    token: str,
) -> PersonaBatchImportSelection:
    """Consume token once and return selected persona ids."""
    normalized_token = token.strip()
    if not normalized_token:
        raise PersonaBatchImportTokenNotFoundError("Import token is required")

    now_ms = _now_ms()
    async with _memory_lock:
        await _cleanup_memory_store(now_ms)
        record = _memory_store.get(normalized_token)
        if record is None:
            raise PersonaBatchImportTokenNotFoundError("Import token expired or already consumed")
        payload, _expires_at_ms = record

        if not isinstance(payload, dict):
            raise PersonaBatchImportStoreError("Invalid import token payload")

        payload_admin_id = payload.get("admin_id")
        if not isinstance(payload_admin_id, int) or payload_admin_id <= 0:
            raise PersonaBatchImportStoreError("Invalid import token owner")
        if payload_admin_id != admin_id:
            raise PersonaBatchImportTokenForbiddenError(
                "Import token does not belong to current admin"
            )

        raw_ids = payload.get("persona_ids")
        if not isinstance(raw_ids, list):
            raise PersonaBatchImportStoreError("Invalid import token persona list")
        persona_ids = _normalize_persona_ids(raw_ids)
        if not persona_ids:
            raise PersonaBatchImportStoreError("Import token has no valid personas")

        created_at_ms = int(payload.get("created_at_ms") or 0)
        expires_at_ms = int(payload.get("expires_at_ms") or 0)
        if expires_at_ms > 0 and now_ms >= expires_at_ms:
            _memory_store.pop(normalized_token, None)
            raise PersonaBatchImportTokenNotFoundError("Import token expired or already consumed")

        _memory_store.pop(normalized_token, None)

    return PersonaBatchImportSelection(
        admin_id=payload_admin_id,
        persona_ids=persona_ids,
        created_at_ms=created_at_ms,
        expires_at_ms=expires_at_ms,
    )
