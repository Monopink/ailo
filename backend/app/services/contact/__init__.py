"""
Contact service module.

This module provides business logic for contact management.
"""

# Contact request processing
from .request_service import (
    accept_contact_request_service,
    create_contact_request_service,
    get_ai_contact_limit,
    get_contact_requests_service,
    ignore_contact_request_service,
)

# Contact basic management
from .service import (
    block_contact,
    delete_contact,
    get_contact_with_profile,
    get_user_contacts_with_profiles,
    unblock_contact,
    update_contact,
)

__all__ = [
    # Contact basic management
    "get_user_contacts_with_profiles",
    "get_contact_with_profile",
    "update_contact",
    "block_contact",
    "unblock_contact",
    "delete_contact",
    # Contact request processing
    "create_contact_request_service",
    "get_contact_requests_service",
    "accept_contact_request_service",
    "ignore_contact_request_service",
    "get_ai_contact_limit",
]
