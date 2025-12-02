"""
Message security layer.

Handles encryption, decryption, and validation.
"""

from .encryption import decrypt_from_transport, encrypt_for_transport

__all__ = [
    "decrypt_from_transport",
    "encrypt_for_transport",
]
