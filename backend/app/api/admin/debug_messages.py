"""Admin debug endpoints for Chat Console observability.

These endpoints are gated by admin session (see app.api.admin.__init__)
and are always available to authenticated admin sessions.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import and_, case, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.enums import ContactType
from app.models.ai.instance import AIInstance
from app.models.ai.log import AIRequestLog
from app.models.ai.memory import AIInstanceMemory
from app.models.ai.template import AIPersona
from app.models.contact import Contact
from app.models.message import MessageHistory
from app.services.ai.queries import get_instance_context
from app.type_defs import CurrentRelationship, InstanceContext, JSONDict, ProfileInfo

router = APIRouter(prefix="/debug/messages", tags=["Admin Debug"])
instance_router = APIRouter(prefix="/debug/instances", tags=["Admin Debug"])

MEMORY_SNAPSHOT_LIMIT = 8
MEMORY_ITEM_MAX_CHARS = 220
SUMMARY_PREVIEW_MAX_CHARS = 700
SYSTEM_PROMPT_PREVIEW_MAX_CHARS = 1600


class DebugLLMRequestDetailRequest(BaseModel):
    """Request payload for querying request/response details by llm_request_id."""

    llm_request_id: str = Field(..., min_length=1, description="llm_request_id")


class DebugLLMLinksRequest(BaseModel):
    """Request payload for resolving llm_request_id by msg_id_server."""

    msg_id_servers: list[str] = Field(..., min_length=1, description="msg_id_server list")


class DebugLLMLinkItem(BaseModel):
    """Single msg_id_server -> llm_request_id link item."""

    msg_id_server: str
    llm_request_id: str | None


class DebugLLMLinksResponse(BaseModel):
    """Response payload for llm links query."""

    links: list[DebugLLMLinkItem]


class DebugLLMRequestDetailSummary(BaseModel):
    """Parsed summary extracted from ai_request_logs.response."""

    should_reply: bool | None = None
    should_block: bool | None = None
    attack_detected: bool | None = None
    should_update_memory: bool | None = None
    outgoing_messages_count: int = 0
    followup_messages_count: int = 0
    memory_operations_count: int = 0
    score_keys: list[str] = Field(default_factory=list)
    finish_reason: str | None = None
    system_prompt_preview: str | None = None
    internal_thoughts_preview: str | None = None
    current_state_preview: str | None = None
    outgoing_messages_preview: str | None = None
    followup_messages_preview: str | None = None
    score_updates_preview: str | None = None
    relationship_selection_preview: str | None = None
    memory_operations_preview: str | None = None


class DebugLLMRequestDetailItem(BaseModel):
    """Single llm_request_id detail record for debug rendering."""

    llm_request_id: str
    found: bool
    status: int | None = None
    provider_name: str | None = None
    model_name: str | None = None
    response_time_ms: int | None = None
    token_count: int | None = None
    created_at: str | None = None
    request_preview: str | None = None
    response_preview: str | None = None
    summary: DebugLLMRequestDetailSummary | None = None


class DebugLLMRequestDetailResponse(BaseModel):
    """Response payload for llm_request_id detail query."""

    detail: DebugLLMRequestDetailItem


class DebugInstanceSnapshotRequest(BaseModel):
    """Request payload for querying an instance debug snapshot."""

    conversation_id: str | None = Field(
        default=None,
        description="conversation_id from contacts (preferred)",
    )
    instance_qiao_id: str | None = Field(
        default=None,
        description="instance qiao_id when conversation_id is unavailable",
    )
    user_qiao_id: str | None = Field(
        default=None,
        description="owner user qiao_id for strict disambiguation",
    )

    @model_validator(mode="after")
    def validate_selector(self) -> DebugInstanceSnapshotRequest:
        """Ensure at least one selector is provided."""
        if not self.conversation_id and not self.instance_qiao_id:
            raise ValueError("conversation_id or instance_qiao_id is required")
        return self


class DebugInstanceMemoryItem(BaseModel):
    """Compact memory row for debug panel display."""

    memory_type: str
    importance: int
    content: str


class DebugInstanceSnapshotResponse(BaseModel):
    """Aggregated instance snapshot for Chat Console debug panel."""

    instance_id: int
    instance_qiao_id: str
    persona_id: int | None
    contact_username: str | None
    user_qiao_id: str
    conversation_id: str | None
    profile: ProfileInfo | None
    style: dict[str, object]
    personality: dict[str, object]
    relationship: CurrentRelationship | None
    memory_items: list[DebugInstanceMemoryItem]


def _truncate_memory_content(content: str) -> str:
    """Trim memory content for compact panel rendering."""
    if len(content) <= MEMORY_ITEM_MAX_CHARS:
        return content
    return f"{content[:MEMORY_ITEM_MAX_CHARS]}..."


def _as_json_dict(value: object) -> JSONDict | None:
    """Coerce generic JSONB payload into JSONDict."""
    if isinstance(value, dict):
        return value
    return None


def _json_preview(value: object, *, max_chars: int | None = None) -> str | None:
    """Build pretty JSON text for debug display."""
    if value is None:
        return None
    try:
        text = json.dumps(value, ensure_ascii=False, indent=2, default=str)
    except TypeError:
        text = str(value)
    if max_chars is None:
        return text
    if len(text) <= max_chars:
        return text
    return f"{text[:max_chars]}..."


def _preview_text(value: object, *, max_chars: int = SUMMARY_PREVIEW_MAX_CHARS) -> str | None:
    """Render scalar/list/json values into compact readable text."""
    if value is None:
        return None

    if isinstance(value, str):
        text = value.strip()
    elif isinstance(value, list):
        text = "\n".join(str(item) for item in value)
    else:
        text = _json_preview(value, max_chars=max_chars) or ""

    if not text:
        return None
    if len(text) <= max_chars:
        return text
    return f"{text[:max_chars]}..."


def _extract_request_messages(request_payload: JSONDict | None) -> list[JSONDict]:
    """Extract message list from supported request payload variants."""
    if request_payload is None:
        return []

    containers: list[object] = [
        request_payload.get("input"),
        request_payload.get("messages"),
    ]
    call_params = _as_json_dict(request_payload.get("call_params"))
    if call_params is not None:
        containers.extend([call_params.get("input"), call_params.get("messages")])
    nested_payload = _as_json_dict(request_payload.get("payload"))
    if nested_payload is not None:
        containers.extend([nested_payload.get("input"), nested_payload.get("messages")])

    for candidate in containers:
        if isinstance(candidate, list):
            return [item for item in candidate if isinstance(item, dict)]
    return []


def _extract_system_prompt_preview(request_payload: JSONDict | None) -> str | None:
    """Extract compact system prompt text from request payload."""
    messages = _extract_request_messages(request_payload)
    if not messages:
        return None

    chunks: list[str] = []
    for message in messages:
        if message.get("role") != "system":
            continue
        content = message.get("content")
        if isinstance(content, str):
            text = content.strip()
            if text:
                chunks.append(text)
            continue
        if isinstance(content, list):
            block_parts: list[str] = []
            for block in content:
                if not isinstance(block, dict):
                    continue
                block_text = block.get("text")
                if isinstance(block_text, str) and block_text.strip():
                    block_parts.append(block_text.strip())
            if block_parts:
                chunks.append("\n".join(block_parts))

    if not chunks:
        return None
    joined = "\n\n".join(chunks)
    if len(joined) <= SYSTEM_PROMPT_PREVIEW_MAX_CHARS:
        return joined
    return f"{joined[:SYSTEM_PROMPT_PREVIEW_MAX_CHARS]}..."


def _parse_llm_request_id(raw_value: str) -> int:
    """Parse llm_request_id from API payload as integer Snowflake ID."""
    value = raw_value.strip()
    if not value or not value.isdigit():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid llm_request_id: {raw_value}",
        )
    return int(value)


def _parse_llm_request_summary(
    response_payload: JSONDict | None,
    request_payload: JSONDict | None,
) -> DebugLLMRequestDetailSummary | None:
    """Extract high-signal fields from ai_request_logs.response payload."""
    if response_payload is None:
        system_prompt_preview = _extract_system_prompt_preview(request_payload)
        if system_prompt_preview is None:
            return None
        return DebugLLMRequestDetailSummary(system_prompt_preview=system_prompt_preview)

    conversation_payload = _as_json_dict(response_payload.get("conversation"))
    outgoing_messages = response_payload.get("outgoing_messages")
    if not isinstance(outgoing_messages, list) and conversation_payload is not None:
        outgoing_messages = conversation_payload.get("outgoing_messages")
    followup_messages = response_payload.get("followup_messages")
    if not isinstance(followup_messages, list) and conversation_payload is not None:
        followup_messages = conversation_payload.get("followup_messages")
    memory_operations = response_payload.get("memory_operations")
    if memory_operations is None and conversation_payload is not None:
        memory_operations = conversation_payload.get("memory_operations")
    score_payload = response_payload.get("score")
    if not isinstance(score_payload, dict) and conversation_payload is not None:
        score_payload = conversation_payload.get("score_updates")
    llm_response = _as_json_dict(response_payload.get("__llm_response"))
    relationship_selection = response_payload.get("selected_relationship_after")
    if relationship_selection is None and conversation_payload is not None:
        relationship_selection = conversation_payload.get("selected_relationship_after")
    internal_thoughts = response_payload.get("internal_thoughts")
    if internal_thoughts is None and conversation_payload is not None:
        internal_thoughts = conversation_payload.get("internal_thoughts")
    current_state = response_payload.get("current_state")
    if current_state is None and conversation_payload is not None:
        current_state = conversation_payload.get("current_state")

    score_keys = sorted(score_payload.keys()) if isinstance(score_payload, dict) else []

    return DebugLLMRequestDetailSummary(
        should_reply=(
            bool(response_payload["should_reply"])
            if isinstance(response_payload.get("should_reply"), bool)
            else None
        ),
        should_block=(
            bool(response_payload["should_block"])
            if isinstance(response_payload.get("should_block"), bool)
            else None
        ),
        attack_detected=(
            bool(response_payload["attack_detected"])
            if isinstance(response_payload.get("attack_detected"), bool)
            else None
        ),
        should_update_memory=(
            bool(response_payload["should_update_memory"])
            if isinstance(response_payload.get("should_update_memory"), bool)
            else None
        ),
        outgoing_messages_count=len(outgoing_messages)
        if isinstance(outgoing_messages, list)
        else 0,
        followup_messages_count=len(followup_messages)
        if isinstance(followup_messages, list)
        else 0,
        memory_operations_count=len(memory_operations)
        if isinstance(memory_operations, list)
        else 0,
        score_keys=score_keys,
        finish_reason=(
            str(llm_response["finish_reason"])
            if llm_response and isinstance(llm_response.get("finish_reason"), str)
            else None
        ),
        system_prompt_preview=_extract_system_prompt_preview(request_payload),
        internal_thoughts_preview=_preview_text(internal_thoughts),
        current_state_preview=_preview_text(current_state),
        outgoing_messages_preview=_preview_text(outgoing_messages),
        followup_messages_preview=_preview_text(followup_messages),
        score_updates_preview=_preview_text(score_payload),
        relationship_selection_preview=_preview_text(relationship_selection),
        memory_operations_preview=_preview_text(memory_operations),
    )


async def get_llm_request_detail(
    db: AsyncSession, *, llm_request_id: str
) -> DebugLLMRequestDetailResponse:
    """Query ai_request_logs details by a single llm_request_id."""
    parsed_id = _parse_llm_request_id(llm_request_id)
    llm_request_id_text = str(parsed_id)
    result = await db.execute(select(AIRequestLog).where(AIRequestLog.id == parsed_id))
    row = result.scalars().first()

    if row is None:
        return DebugLLMRequestDetailResponse(
            detail=DebugLLMRequestDetailItem(llm_request_id=llm_request_id_text, found=False)
        )

    response_payload = _as_json_dict(row.response)
    detail = DebugLLMRequestDetailItem(
        llm_request_id=llm_request_id_text,
        found=True,
        status=row.status,
        provider_name=row.provider_name,
        model_name=row.model_name,
        response_time_ms=row.response_time,
        token_count=row.token_count,
        created_at=row.created_at.isoformat() if row.created_at else None,
        request_preview=_json_preview(row.request),
        response_preview=_json_preview(row.response),
        summary=_parse_llm_request_summary(
            response_payload=response_payload,
            request_payload=_as_json_dict(row.request),
        ),
    )
    return DebugLLMRequestDetailResponse(detail=detail)


async def get_llm_links(
    db: AsyncSession,
    *,
    msg_id_servers: list[str],
) -> DebugLLMLinksResponse:
    """Query message_history for llm_request_id by msg_id_server."""
    result = await db.execute(
        select(MessageHistory.msg_id_server, MessageHistory.llm_request_id).where(
            MessageHistory.msg_id_server.in_(msg_id_servers)
        )
    )
    rows = result.all()
    llm_map = {row[0]: row[1] for row in rows}
    links: list[DebugLLMLinkItem] = []
    for msg_id_server in msg_id_servers:
        llm_request_id = llm_map.get(msg_id_server)
        links.append(
            DebugLLMLinkItem(
                msg_id_server=msg_id_server,
                llm_request_id=str(llm_request_id) if llm_request_id is not None else None,
            )
        )
    return DebugLLMLinksResponse(links=links)


async def _resolve_contact_selector(
    db: AsyncSession,
    *,
    conversation_id: str | None,
    user_qiao_id: str | None,
) -> Contact | None:
    """Resolve contact by conversation_id (optionally scoped by user_qiao_id)."""
    if not conversation_id:
        return None

    stmt = select(Contact).where(
        and_(
            Contact.conversation_id == conversation_id,
            Contact.contact_type == ContactType.AI,
            Contact.is_deleted == 0,
        )
    )
    if user_qiao_id:
        stmt = stmt.where(Contact.user_qiao_id == user_qiao_id)
    result = await db.execute(stmt)
    return result.scalars().first()


async def _resolve_context(
    db: AsyncSession,
    payload: DebugInstanceSnapshotRequest,
) -> tuple[InstanceContext, str | None]:
    """Resolve instance context using conversation selector first."""
    contact = await _resolve_contact_selector(
        db,
        conversation_id=payload.conversation_id,
        user_qiao_id=payload.user_qiao_id,
    )

    if contact is not None:
        context = await get_instance_context(
            db,
            instance_qiao_id=contact.contact_qiao_id,
            user_qiao_id=contact.user_qiao_id,
        )
        if context is not None:
            return context, contact.conversation_id

    if payload.instance_qiao_id:
        stmt = select(AIInstance).where(AIInstance.qiao_id == payload.instance_qiao_id)
        if payload.user_qiao_id:
            stmt = stmt.where(AIInstance.user_qiao_id == payload.user_qiao_id)
        result = await db.execute(stmt)
        instance = result.scalars().first()
        if instance is not None:
            context = await get_instance_context(db, instance_id=instance.id)
            if context is not None:
                return context, payload.conversation_id

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Instance snapshot target not found",
    )


async def get_instance_snapshot(
    db: AsyncSession,
    payload: DebugInstanceSnapshotRequest,
) -> DebugInstanceSnapshotResponse:
    """Build aggregated instance snapshot response."""
    context, conversation_id = await _resolve_context(db, payload)
    memory_rows_result = await db.execute(
        select(AIInstanceMemory)
        .where(
            and_(
                AIInstanceMemory.instance_qiao_id == context["instance_qiao_id"],
                AIInstanceMemory.user_qiao_id == context["user_qiao_id"],
                AIInstanceMemory.status == 1,
            )
        )
        .order_by(
            case((AIInstanceMemory.memory_type == "core", 0), else_=1),
            AIInstanceMemory.source_strength.desc(),
            AIInstanceMemory.importance.desc(),
            AIInstanceMemory.reinforce_count.desc(),
            AIInstanceMemory.updated_at.desc(),
            AIInstanceMemory.created_at.desc(),
            AIInstanceMemory.id.desc(),
        )
        .limit(MEMORY_SNAPSHOT_LIMIT)
    )
    memory_rows = list(memory_rows_result.scalars().all())
    memory_items = [
        DebugInstanceMemoryItem(
            memory_type=row.memory_type,
            importance=row.importance,
            content=_truncate_memory_content(row.content),
        )
        for row in memory_rows
    ]

    style = context["style"]
    personality = context["personality"]
    relationship = context.get("current_relationship")
    identity_result = await db.execute(
        select(AIInstance.persona_id, AIPersona.username)
        .select_from(AIInstance)
        .outerjoin(AIPersona, AIInstance.persona_id == AIPersona.id)
        .where(AIInstance.id == context["instance_id"])
    )
    identity_row = identity_result.first()
    persona_id: int | None = None
    contact_username: str | None = None
    if identity_row is not None:
        persona_id = identity_row[0] if isinstance(identity_row[0], int) else None
        contact_username = identity_row[1] if isinstance(identity_row[1], str) else None

    return DebugInstanceSnapshotResponse(
        instance_id=context["instance_id"],
        instance_qiao_id=context["instance_qiao_id"],
        persona_id=persona_id,
        contact_username=contact_username,
        user_qiao_id=context["user_qiao_id"],
        conversation_id=conversation_id,
        profile=context.get("profile"),
        style={
            "id": style["id"],
            "display_name": style["display_name"],
        },
        personality={
            "id": personality["id"],
            "display_name": personality["display_name"],
        },
        relationship=relationship,
        memory_items=memory_items,
    )


@router.post("/llm-request-detail", response_model=DebugLLMRequestDetailResponse)
async def debug_llm_request_detail(
    payload: DebugLLMRequestDetailRequest,
    db: AsyncSession = Depends(get_db),
) -> DebugLLMRequestDetailResponse:
    """Resolve parsed request/response detail for llm_request_id."""
    return await get_llm_request_detail(db, llm_request_id=payload.llm_request_id)


@router.post("/llm-links", response_model=DebugLLMLinksResponse)
async def debug_llm_links(
    payload: DebugLLMLinksRequest,
    db: AsyncSession = Depends(get_db),
) -> DebugLLMLinksResponse:
    """Resolve llm_request_id for a batch of msg_id_server values."""
    return await get_llm_links(db, msg_id_servers=payload.msg_id_servers)


@instance_router.post("/snapshot", response_model=DebugInstanceSnapshotResponse)
async def debug_instance_snapshot(
    payload: DebugInstanceSnapshotRequest,
    db: AsyncSession = Depends(get_db),
) -> DebugInstanceSnapshotResponse:
    """Resolve style/personality/relationship/memory snapshot for Chat Console."""
    return await get_instance_snapshot(db, payload)
