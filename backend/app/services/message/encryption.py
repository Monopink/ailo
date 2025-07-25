"""
Message Encryption Module

Pure encryption and decryption utilities.
Provides algorithm-agnostic functions for encrypting and decrypting content.
"""

import base64
import secrets
from typing import Dict, Any, Tuple
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from enums import EncryptionType, EncryptionVersion
from utils.logging import get_logger

logger = get_logger(__name__)


def encrypt(content: str, algorithm: EncryptionType, key: bytes) -> Tuple[str, Dict[str, Any]]:
    """
    Encrypt content using specified algorithm and key.

    Args:
        content: Plain text content to encrypt
        algorithm: Encryption algorithm to use
        key: Encryption key (algorithm-specific format)

    Returns:
        Tuple of (encrypted_content, metadata)

    Raises:
        ValueError: If parameters are invalid or encryption fails
    """
    if not content or not isinstance(content, str):
        raise ValueError("Content must be a non-empty string")

    if not isinstance(algorithm, EncryptionType):
        raise ValueError("Algorithm must be an EncryptionType enum")

    if not isinstance(key, bytes):
        raise ValueError("Key must be bytes")

    try:
        if algorithm == EncryptionType.BASE64:
            return _encode_base64(content)
        elif algorithm == EncryptionType.AES_256_GCM:
            return _encrypt_aes_256_gcm(content, key)
        else:
            raise ValueError(f"Unsupported encryption algorithm: {algorithm}")

    except Exception as e:
        logger.error("encryption_failed", algorithm=algorithm.name, error=str(e))
        raise ValueError(f"Encryption failed: {str(e)}")


def decrypt(encrypted_content: str, metadata: Dict[str, Any], key: bytes) -> str:
    """
    Decrypt content using metadata and key.

    Args:
        encrypted_content: Encrypted content string
        metadata: Encryption metadata containing algorithm and parameters
        key: Decryption key (algorithm-specific format)

    Returns:
        str: Decrypted plain text content

    Raises:
        ValueError: If parameters are invalid or decryption fails
    """
    if not encrypted_content or not isinstance(encrypted_content, str):
        raise ValueError("Encrypted content must be a non-empty string")

    if not isinstance(metadata, dict):
        raise ValueError("Metadata must be a dictionary")

    if not isinstance(key, bytes):
        raise ValueError("Key must be bytes")

    try:
        # Extract algorithm from metadata
        algorithm_value = metadata.get("encryption")
        if algorithm_value is None:
            raise ValueError("Missing encryption algorithm in metadata")

        algorithm = EncryptionType(algorithm_value)

        if algorithm == EncryptionType.BASE64:
            return _decode_base64(encrypted_content)
        elif algorithm == EncryptionType.AES_256_GCM:
            return _decrypt_aes_256_gcm(encrypted_content, metadata, key)
        else:
            raise ValueError(f"Unsupported encryption algorithm: {algorithm}")

    except Exception as e:
        logger.error("decryption_failed", metadata=metadata, error=str(e))
        raise ValueError(f"Decryption failed: {str(e)}")


def _encode_base64(content: str) -> Tuple[str, Dict[str, Any]]:
    """
    Encrypt content using Base64 encoding.

    Args:
        content: Plain text content

    Returns:
        Tuple of (encrypted_content, metadata)
    """
    # Encode to bytes, then to base64
    content_bytes = content.encode("utf-8")
    encoded_bytes = base64.b64encode(content_bytes)
    encrypted_content = encoded_bytes.decode("utf-8")

    metadata = {
        "encryption": EncryptionType.BASE64.value,
        "enc_version": EncryptionVersion.V1.value,
    }

    logger.debug(
        "base64_encryption_completed", original_length=len(content), encrypted_length=len(encrypted_content)
    )

    return encrypted_content, metadata


def _decode_base64(encrypted_content: str) -> str:
    """
    Decrypt content using Base64 decoding.

    Args:
        encrypted_content: Base64 encrypted content

    Returns:
        str: Decrypted plain text content
    """
    # Decode from base64, then to string
    encoded_bytes = encrypted_content.encode("utf-8")
    content_bytes = base64.b64decode(encoded_bytes)
    decrypted_content = content_bytes.decode("utf-8")

    logger.debug(
        "base64_decryption_completed",
        encrypted_length=len(encrypted_content),
        decrypted_length=len(decrypted_content),
    )

    return decrypted_content


def _encrypt_aes_256_gcm(content: str, key: bytes) -> Tuple[str, Dict[str, Any]]:
    """
    Encrypt content using AES-256-GCM.

    Args:
        content: Plain text content
        key: 32-byte AES key

    Returns:
        Tuple of (encrypted_content, metadata)
    """
    if len(key) != 32:
        raise ValueError("AES-256 key must be 32 bytes")

    # Generate random IV (12 bytes for GCM)
    iv = secrets.token_bytes(12)

    # Create AESGCM cipher
    aesgcm = AESGCM(key)

    # Encrypt content
    content_bytes = content.encode("utf-8")
    encrypted_bytes = aesgcm.encrypt(iv, content_bytes, None)

    # Encode encrypted content and IV to base64
    encrypted_content = base64.b64encode(encrypted_bytes).decode("utf-8")
    iv_b64 = base64.b64encode(iv).decode("utf-8")

    metadata = {
        "encryption": EncryptionType.AES_256_GCM.value,
        "enc_version": EncryptionVersion.V1.value,
        "iv": iv_b64,
    }

    logger.debug(
        "aes_256_gcm_encryption_completed",
        original_length=len(content),
        encrypted_length=len(encrypted_content),
    )

    return encrypted_content, metadata


def _decrypt_aes_256_gcm(encrypted_content: str, metadata: Dict[str, Any], key: bytes) -> str:
    """
    Decrypt content using AES-256-GCM.

    Args:
        encrypted_content: Base64 encoded encrypted content
        metadata: Encryption metadata containing IV
        key: 32-byte AES key

    Returns:
        str: Decrypted plain text content
    """
    if len(key) != 32:
        raise ValueError("AES-256 key must be 32 bytes")

    # Extract IV from metadata
    iv_b64 = metadata.get("iv")
    if not iv_b64:
        raise ValueError("Missing IV in metadata")

    try:
        # Decode IV and encrypted content from base64
        iv = base64.b64decode(iv_b64.encode("utf-8"))
        encrypted_bytes = base64.b64decode(encrypted_content.encode("utf-8"))

        # Create AESGCM cipher
        aesgcm = AESGCM(key)

        # Decrypt content
        decrypted_bytes = aesgcm.decrypt(iv, encrypted_bytes, None)
        decrypted_content = decrypted_bytes.decode("utf-8")

        logger.debug(
            "aes_256_gcm_decryption_completed",
            encrypted_length=len(encrypted_content),
            decrypted_length=len(decrypted_content),
        )

        return decrypted_content

    except Exception as e:
        raise ValueError(f"AES-256-GCM decryption failed: {str(e)}")
