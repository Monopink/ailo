"""Growth attribution and redeem code schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.common import BaseSchema


class GrowthAttributionTrackRequest(BaseModel):
    """Track campaign attribution request payload."""

    campaign_code: str = Field(..., min_length=3, max_length=32)
    source: str = Field(..., min_length=1, max_length=32)
    payload: dict[str, object] | None = Field(default=None)


class GrowthAttributionTrackResponse(BaseSchema):
    """Track attribution response payload."""

    accepted: bool = Field(...)
    attributed: bool = Field(...)


class RedeemCodeClaimRequest(BaseModel):
    """Redeem claim request payload."""

    code: str = Field(..., min_length=4, max_length=32)


class RedeemCodeClaimResponse(BaseSchema):
    """Redeem claim response payload."""

    claimed: bool = Field(...)
    reward_contact_limit: int = Field(..., ge=0)
