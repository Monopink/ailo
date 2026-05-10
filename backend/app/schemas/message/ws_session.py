"""WebSocket session bootstrap schemas."""

from pydantic import BaseModel, Field


class MessageWSSessionTicketRequest(BaseModel):
    """WebSocket session ticket request payload."""

    device_id: str = Field(..., description="Device/installation UUID")


class MessageWSSessionAuth(BaseModel):
    """Auth payload for websocket transport bootstrap."""

    scheme: str = Field(default="ws_ticket")
    version: str = Field(default="1")
    ws_ticket: str
    issued_at_ms: int
    device_id: str
    expires_in_ms: int


class MessageWSSessionPayload(BaseModel):
    """Session payload returned by ws-session bootstrap."""

    client_id: str
    provider: str = Field(default="websocket")
    server_url: str
    session_hint: str = Field(default="__ws__")
    auth: MessageWSSessionAuth


class MessageWSPresencePayload(BaseModel):
    """Presence placeholder payload kept for bootstrap shape compatibility."""

    endpoint_id: int = 0
    lease_ttl_days: int = 0
    lease_expires_at_ms: int = 0


class MessageWSSessionBootstrapResponse(BaseModel):
    """WebSocket session bootstrap response payload."""

    config_version: str
    session: MessageWSSessionPayload
    presence: MessageWSPresencePayload
