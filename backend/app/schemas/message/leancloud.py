"""LeanCloud messaging schemas."""

from pydantic import BaseModel, Field


class LeanCloudConfigResponse(BaseModel):
    """Public LeanCloud configuration returned to clients."""

    im_conv_id: str = Field(..., description="System conversation identifier used by LeanCloud")
    signature_algorithm: str = Field(..., description="Signature algorithm identifier")
    signature_version: str = Field(..., description="Signature protocol version")
    signature_ttl_ms: int = Field(..., description="Signature TTL in milliseconds")


class LeanCloudSignatureRequest(BaseModel):
    """Signature generation request payload."""

    client_id: str = Field(..., description="Client ID, must match user's qiao_id")


class LeanCloudSignatureResponse(BaseModel):
    """Signature generation response payload."""

    client_id: str = Field(..., description="Client ID echoed back to caller")
    signature: str = Field(..., description="HMAC-SHA1 signature")
    timestamp: int = Field(..., description="Timestamp in milliseconds when signature was created")
    nonce: str = Field(..., description="Random nonce tied to signature")
    expires_in: int = Field(..., description="Signature TTL in seconds")
