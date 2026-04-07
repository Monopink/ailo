"""LeanCloud messaging schemas."""

from pydantic import BaseModel, Field


class LeanCloudBootstrapRequest(BaseModel):
    """Client bootstrap request payload."""

    client_kind: int | None = Field(
        default=None,
        description="Optional client kind enum (DeviceType)",
    )


class LeanCloudBootstrapSignature(BaseModel):
    """LeanCloud login signature payload."""

    algorithm: str = Field(..., description="Signature algorithm identifier")
    version: str = Field(..., description="Signature protocol version")
    value: str = Field(..., description="Signature value")
    timestamp: int = Field(..., description="Signature timestamp in milliseconds")
    nonce: str = Field(..., description="Signature nonce")
    expires_in_ms: int = Field(..., description="Signature TTL in milliseconds")


class LeanCloudBootstrapConfig(BaseModel):
    """Client connection config payload."""

    client_id: str = Field(..., description="LeanCloud client ID for current user")
    app_id: str = Field(..., description="LeanCloud App ID")
    app_key: str = Field(..., description="LeanCloud App Key")
    server_url: str = Field(..., description="LeanCloud server URL")
    im_conv_id: str = Field(..., description="System conversation ID")
    signature: LeanCloudBootstrapSignature = Field(..., description="Login signature data")


class LeanCloudBootstrapPresence(BaseModel):
    """Presence registration result payload."""

    endpoint_id: int = Field(..., description="Registered message_endpoints.id")
    lease_ttl_days: int = Field(..., description="Endpoint lease TTL in days")
    lease_expires_at_ms: int = Field(..., description="Lease expiry timestamp in milliseconds")


class LeanCloudBootstrapResponse(BaseModel):
    """Bootstrap response payload."""

    config_version: str = Field(..., description="Configuration version identifier")
    session: LeanCloudBootstrapConfig = Field(..., description="Session connection data")
    presence: LeanCloudBootstrapPresence = Field(..., description="Presence lease data")
