"""
Contact service module.

This module provides business logic for contact management.
"""

# Contact basic management
from .service import (
    get_user_contacts_with_profiles,
    get_contact_with_profile,
    get_conversation_info,
    update_contact,
    block_contact,
    unblock_contact,
    delete_contact,
)

# Contact request processing
from .request_service import (
    create_contact_request_service,
    get_contact_requests_service,
    accept_contact_request_service,
    reject_contact_request_service,
    get_ai_contact_limit,
)

__all__ = [
    # Contact basic management
    "get_user_contacts_with_profiles",
    "get_contact_with_profile",
    "get_conversation_info",
    "update_contact",
    "block_contact",
    "unblock_contact",
    "delete_contact",
    # Contact request processing
    "create_contact_request_service",
    "get_contact_requests_service",
    "accept_contact_request_service",
    "reject_contact_request_service",
    "get_ai_contact_limit",
]
