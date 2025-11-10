"""
Conversation schemas.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class ConversationStateResponse(BaseModel):
    """Represents the current messaging conversation state."""

    im_conv_id: str
    version: str
    updated_at: Optional[datetime] = None
