"""Conversation schemas."""

from pydantic import BaseModel


class ConversationStateResponse(BaseModel):
    """Represents the current system messaging conversation state."""

    im_conv_id: str
