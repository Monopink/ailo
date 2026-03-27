"""
Minimal-contract validators for AI responses.

These validators implement the runtime L0 gate (hard requirements) and L1 pruning
(best-effort fields). They must stay pure (no DB/session access).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.ai.response_schema import (
    get_score_dimension_bounds,
    validate_style_personality_contract,
)
from app.services.ai.utils.normalization import normalize_memory_operations
from app.type_defs import JSONDict, JSONValue

# Constant switch (code-level only, not system_config).
# Default (Mode B): when should_reply=false but message arrays are valid and non-empty,
# ignore messages and do not treat as L0 failure.
STRICT_SHOULD_REPLY_FALSE_WITH_MESSAGES = False


@dataclass(frozen=True, slots=True)
class L0ContractResult:
    ok: bool
    failure_code: str | None
    failure_detail: str | None
    attack_detected: bool | None = None
    should_block: bool | None = None
    should_reply: bool | None = None
    outgoing_messages: list[str] | None = None
    followup_messages: list[str] | None = None
    reply_messages_ignored: bool = False


@dataclass(frozen=True, slots=True)
class L1PruneResult:
    pruned_response: JSONDict
    score_kept: bool
    memory_kept: bool


def _require_bool(payload: JSONDict, key: str) -> bool:
    value = payload.get(key)
    if isinstance(value, bool):
        return value
    raise TypeError(f"{key} must be boolean")


def _normalize_message_list(value: JSONValue | None, *, field_name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise TypeError(f"{field_name} must be string[]")

    normalized: list[str] = []
    for idx, item in enumerate(value):
        if not isinstance(item, str):
            raise TypeError(f"{field_name}[{idx}] must be string")
        text = item.strip()
        if not text:
            raise ValueError(f"{field_name}[{idx}] cannot be empty string")
        normalized.append(text)
    return normalized


def _build_l0_success_result(
    *,
    attack_detected: bool,
    should_block: bool,
    should_reply: bool,
    outgoing_messages: list[str],
    followup_messages: list[str],
    reply_messages_ignored: bool = False,
) -> L0ContractResult:
    return L0ContractResult(
        ok=True,
        failure_code=None,
        failure_detail=None,
        attack_detected=attack_detected,
        should_block=should_block,
        should_reply=should_reply,
        outgoing_messages=outgoing_messages,
        followup_messages=followup_messages,
        reply_messages_ignored=reply_messages_ignored,
    )


def _validate_should_reply_true(
    *,
    attack_detected: bool,
    should_block: bool,
    should_reply: bool,
    outgoing_messages: list[str],
    followup_messages: list[str],
) -> L0ContractResult:
    if not outgoing_messages and not followup_messages:
        return L0ContractResult(
            ok=False,
            failure_code="L0_EMPTY_MESSAGES",
            failure_detail=(
                "should_reply=true but both outgoing_messages and followup_messages are empty"
            ),
        )
    return _build_l0_success_result(
        attack_detected=attack_detected,
        should_block=should_block,
        should_reply=should_reply,
        outgoing_messages=outgoing_messages,
        followup_messages=followup_messages,
    )


def _validate_should_reply_false(
    *,
    strict_should_reply_false_with_messages: bool,
    attack_detected: bool,
    should_block: bool,
    should_reply: bool,
    outgoing_messages: list[str],
    followup_messages: list[str],
) -> L0ContractResult:
    if outgoing_messages or followup_messages:
        if strict_should_reply_false_with_messages:
            return L0ContractResult(
                ok=False,
                failure_code="L0_SHOULD_REPLY_FALSE_WITH_MESSAGES",
                failure_detail="should_reply=false but message arrays are non-empty",
            )
        return _build_l0_success_result(
            attack_detected=attack_detected,
            should_block=should_block,
            should_reply=should_reply,
            outgoing_messages=[],
            followup_messages=[],
            reply_messages_ignored=True,
        )

    return _build_l0_success_result(
        attack_detected=attack_detected,
        should_block=should_block,
        should_reply=should_reply,
        outgoing_messages=[],
        followup_messages=[],
    )


def validate_l0_contract(
    ai_response: object,
    *,
    strict_should_reply_false_with_messages: bool = STRICT_SHOULD_REPLY_FALSE_WITH_MESSAGES,
) -> L0ContractResult:
    """
    Validate runtime L0 minimal contract and normalize message arrays.

    L0 requirements:
    - attack_detected/should_block/should_reply must exist and be boolean.
    - outgoing_messages/followup_messages must be string[] when present
      and contain non-empty strings.
    - if should_reply=true, at least one of outgoing_messages/followup_messages must be non-empty.
    - if should_reply=false, messages may be empty/missing; when present and non-empty:
      - Mode B (default): ignore messages.
      - Mode A (strict): treat as L0 failure.
    """
    if not isinstance(ai_response, dict):
        return L0ContractResult(
            ok=False,
            failure_code="L0_NOT_OBJECT",
            failure_detail="response must be an object",
        )

    try:
        attack_detected = _require_bool(ai_response, "attack_detected")
        should_block = _require_bool(ai_response, "should_block")
        should_reply = _require_bool(ai_response, "should_reply")

        outgoing_messages = _normalize_message_list(
            ai_response.get("outgoing_messages"), field_name="outgoing_messages"
        )
        followup_messages = _normalize_message_list(
            ai_response.get("followup_messages"), field_name="followup_messages"
        )
        if should_reply:
            return _validate_should_reply_true(
                attack_detected=attack_detected,
                should_block=should_block,
                should_reply=should_reply,
                outgoing_messages=outgoing_messages,
                followup_messages=followup_messages,
            )
        return _validate_should_reply_false(
            strict_should_reply_false_with_messages=strict_should_reply_false_with_messages,
            attack_detected=attack_detected,
            should_block=should_block,
            should_reply=should_reply,
            outgoing_messages=outgoing_messages,
            followup_messages=followup_messages,
        )
    except Exception as exc:
        return L0ContractResult(
            ok=False,
            failure_code="L0_INVALID",
            failure_detail=str(exc),
        )


def prune_l1_fields(
    *,
    ai_response: JSONDict,
    style_dimension_names: list[str],
    personality_schema: JSONDict | None,
) -> L1PruneResult:
    """
    Validate and prune L1 optional fields.

    - score: strict validation. Any violation drops the entire score field.
    - memory: if should_update_memory is not boolean or memory_operations is not a dict,
      drop both should_update_memory and memory_operations.

    Notes:
    - Style/personality contract mismatch is treated as a programming/configuration error
      and should be handled by the caller (fail-fast).
    """
    validate_style_personality_contract(style_dimension_names, personality_schema)
    bounds_map = get_score_dimension_bounds(personality_schema)

    pruned: JSONDict = dict(ai_response)

    score_value = pruned.get("score")
    if not isinstance(score_value, dict):
        pruned.pop("score", None)
        score_kept = False
    else:
        score_keys = set(score_value.keys())
        expected_keys = set(style_dimension_names)
        if score_keys != expected_keys:
            pruned.pop("score", None)
            score_kept = False
        else:
            valid = True
            for dim_name in style_dimension_names:
                raw_value = score_value.get(dim_name)
                if isinstance(raw_value, bool) or not isinstance(raw_value, int):
                    valid = False
                    break
                min_v, max_v = bounds_map[dim_name]
                if float(raw_value) < float(min_v) or float(raw_value) > float(max_v):
                    valid = False
                    break
            if not valid:
                pruned.pop("score", None)
                score_kept = False
            else:
                score_kept = True

    should_update_memory = pruned.get("should_update_memory")
    memory_operations = pruned.get("memory_operations")
    if (
        "memory_operations" in pruned and not isinstance(memory_operations, dict)
    ) or not isinstance(should_update_memory, bool):
        pruned.pop("should_update_memory", None)
        pruned.pop("memory_operations", None)
        memory_kept = False
    else:
        normalized_memory_operations = normalize_memory_operations(memory_operations)
        pruned["memory_operations"] = normalized_memory_operations
        has_memory_operations = any(
            normalized_memory_operations[key] for key in ("remove", "update", "refresh_ids", "add")
        )
        memory_kept = bool(should_update_memory) and has_memory_operations

    return L1PruneResult(pruned_response=pruned, score_kept=score_kept, memory_kept=memory_kept)
