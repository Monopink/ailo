"""
Message security layer.

Handles encryption, decryption, and validation.
"""

from .encryption import encrypt_for_transport, decrypt_from_transport

__all__ = [
    "encrypt_for_transport",
    "decrypt_from_transport",
]
