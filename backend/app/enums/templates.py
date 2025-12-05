"""
Chat info message templates.

This module provides template mappings for chat info messages.
Templates are used by business logic to generate consistent messages.

Usage:
    from app.enums.templates import CHAT_INFO_TEMPLATES, ChatInfoType

    content = CHAT_INFO_TEMPLATES[ChatInfoType.CONTACT_ADDED]
    await send_chat_info(db, to_qiao_id=user_id, conv_id=conv_id, content=content)
"""

from app.enums.common import ChatInfoType

# Chat info message templates
CHAT_INFO_TEMPLATES = {
    ChatInfoType.CONTACT_ADDED: "对方已将你添加为联系人",
    ChatInfoType.MESSAGE_BLOCKED: "消息已发出,但对方拒收了",
    ChatInfoType.NOT_FRIEND: "对方还没有添加你为联系人",
}

__all__ = ["CHAT_INFO_TEMPLATES", "ChatInfoType"]
