from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_admin_user_and_db
from app.schemas.contact import ContactRequestRetryPayload
from app.services.contact.request_service import retry_pending_contact_request
from app.type_defs import JSONDict

contact_requests_router = APIRouter(tags=["Admin Contact Requests"])


@contact_requests_router.post("/{request_id}/retry", summary="Retry pending AI contact request")
async def admin_retry_contact_request(
    request_id: int,
    payload: ContactRequestRetryPayload | None = None,
    admin_context: tuple[dict[str, Any], AsyncSession] = Depends(get_admin_user_and_db),
) -> JSONDict:
    """Retry a pending AI contact request that previously failed due to template unavailability.

    This endpoint allows administrators to manually retry contact requests that are stuck
    in PENDING status with a failure_code set (e.g., NO_TEMPLATE_AVAILABLE).

    Args:
        request_id: ID of the contact request to retry
        payload: Optional payload with alias and tags to override
        admin_context: Admin user session and database connection

    Returns:
        Success message indicating retry was triggered

    """
    admin_user, db = admin_context
    alias = payload.alias if payload else None
    tags = payload.tags if payload else None
    return await retry_pending_contact_request(
        db,
        request_id=request_id,
        alias=alias,
        tags=tags,
        operator=admin_user.get("username") if admin_user else None,
    )
