import base64
import logging
from typing import Dict, Any, Optional
from abc import ABC, abstractmethod
from enums import EncryptionType, EncryptionVersion

logger = logging.getLogger(__name__)

# Encryption configuration
ENCRYPTION_CONFIG = {
    "DEFAULT_ALGORITHM": "base64",
    "VERSION": "1.0",
    "SUPPORTED_ALGORITHMS": ["base64"],  # Future: add "aes-256-gcm"
    "DEBUG_LOG_OPERATIONS": True,  # Set to True for debugging
}


class EncryptionInterface(ABC):
    """Abstract interface for encryption algorithms"""

    @abstractmethod
    def encrypt(self, content: str) -> str:
        """Encrypt content and return encrypted string"""
        pass

    @abstractmethod
    def decrypt(self, encrypted_content: str) -> str:
        """Decrypt content and return original string"""
        pass


class Base64Encryption(EncryptionInterface):
    """Base64 encoding implementation (not real encryption)"""

    def encrypt(self, content: str) -> str:
        """Encode content using Base64"""
        if not content or not isinstance(content, str):
            raise ValueError("Content must be a non-empty string")

        try:
            # Encode to bytes, then to base64
            content_bytes = content.encode("utf-8")
            encoded_bytes = base64.b64encode(content_bytes)
            return encoded_bytes.decode("utf-8")
        except Exception as e:
            raise ValueError(f"Base64 encoding failed: {str(e)}")

    def decrypt(self, encrypted_content: str) -> str:
        """Decode Base64 content"""
        if not encrypted_content or not isinstance(encrypted_content, str):
            raise ValueError("Encrypted content must be a non-empty string")

        try:
            # Decode from base64, then to string
            encoded_bytes = encrypted_content.encode("utf-8")
            content_bytes = base64.b64decode(encoded_bytes)
            return content_bytes.decode("utf-8")
        except Exception as e:
            raise ValueError(f"Base64 decoding failed: {str(e)}")


class AESEncryption(EncryptionInterface):
    """Future AES-256-GCM encryption implementation"""

    def __init__(self, key: Optional[bytes] = None):
        self.key = key
        # TODO: Implement proper key management

    def encrypt(self, content: str) -> str:
        """Future AES encryption implementation"""
        # TODO: Implement AES-256-GCM encryption
        raise NotImplementedError("AES encryption not yet implemented")

    def decrypt(self, encrypted_content: str) -> str:
        """Future AES decryption implementation"""
        # TODO: Implement AES-256-GCM decryption
        raise NotImplementedError("AES decryption not yet implemented")


class EncryptionService:
    """Main encryption service for handling message encryption/decryption"""

    def __init__(self):
        self.algorithms = {
            "base64": Base64Encryption(),
            # 'aes-256-gcm': AESEncryption(),  # Future implementation
        }
        self.default_algorithm = ENCRYPTION_CONFIG["DEFAULT_ALGORITHM"]
        self.version = ENCRYPTION_CONFIG["VERSION"]

    def encrypt_message(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Encrypt message content and add encryption metadata

        Args:
            message_data: Original message dictionary

        Returns:
            Encrypted message dictionary with encryption metadata
        """
        if not isinstance(message_data, dict):
            raise ValueError("Message data must be a dictionary")

        # Create a copy to avoid mutating original
        encrypted_message = message_data.copy()

        # Get content to encrypt
        content = encrypted_message.get("content", "")
        if not content:
            # No content to encrypt, return as-is
            return encrypted_message

        try:
            # Get encryption algorithm
            algorithm = self.default_algorithm

            if algorithm not in self.algorithms:
                raise ValueError(f"Unsupported algorithm: {algorithm}")

            # Encrypt the content
            encrypted_content = self.algorithms[algorithm].encrypt(content)

            # Update message with encrypted content
            encrypted_message["content"] = encrypted_content

            # Add encryption metadata using numeric codes
            encrypted_message["encryption"] = EncryptionType.BASE64.value
            encrypted_message["enc_version"] = EncryptionVersion.V1.value

            # Log operation if debugging is enabled
            if ENCRYPTION_CONFIG["DEBUG_LOG_OPERATIONS"]:
                logger.info(
                    f"Message encrypted: algorithm={algorithm}, "
                    f"original_length={len(content)}, "
                    f"encrypted_length={len(encrypted_content)}"
                )

            return encrypted_message

        except Exception as e:
            logger.error(f"Failed to encrypt message: {str(e)}")
            raise ValueError(f"Message encryption failed: {str(e)}")

    def decrypt_message(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Decrypt message content and remove encryption metadata

        Args:
            message_data: Encrypted message dictionary

        Returns:
            Decrypted message dictionary without encryption metadata
        """
        if not isinstance(message_data, dict):
            raise ValueError("Message data must be a dictionary")

        # Create a copy to avoid mutating original
        decrypted_message = message_data.copy()

        # Check if message is encrypted (using new numeric format)
        if not self.is_encrypted(message_data):
            # Not encrypted, return as-is (backward compatibility)
            return decrypted_message

        try:
            # Get encryption metadata (numeric format)
            encryption_type = message_data.get("encryption", 0)

            # Map numeric encryption type to algorithm name
            algorithm_map = {
                EncryptionType.BASE64.value: "base64",
                EncryptionType.AES_256_GCM.value: "aes-256-gcm",
            }
            algorithm = algorithm_map.get(encryption_type, "base64")

            if algorithm not in self.algorithms:
                raise ValueError(f"Unsupported algorithm: {algorithm}")

            # Get encrypted content
            encrypted_content = message_data.get("content", "")

            # Decrypt the content
            decrypted_content = self.algorithms[algorithm].decrypt(encrypted_content)

            # Update message with decrypted content
            decrypted_message["content"] = decrypted_content

            # Remove encryption metadata
            decrypted_message.pop("encryption", None)
            decrypted_message.pop("enc_version", None)

            # Log operation if debugging is enabled
            if ENCRYPTION_CONFIG["DEBUG_LOG_OPERATIONS"]:
                logger.info(
                    f"Message decrypted: algorithm={algorithm}, "
                    f"encrypted_length={len(encrypted_content)}, "
                    f"decrypted_length={len(decrypted_content)}"
                )

            return decrypted_message

        except Exception as e:
            logger.error(f"Failed to decrypt message: {str(e)}")
            raise ValueError(f"Message decryption failed: {str(e)}")

    def is_encrypted(self, message_data: Dict[str, Any]) -> bool:
        """
        Check if a message is encrypted

        Args:
            message_data: Message dictionary to check

        Returns:
            True if message is encrypted, False otherwise
        """
        return (
            isinstance(message_data, dict)
            and "encryption" in message_data
            and isinstance(message_data["encryption"], int)
            and message_data["encryption"] > EncryptionType.NONE.value
            and "enc_version" in message_data
            and isinstance(message_data["enc_version"], int)
        )

    def get_encryption_metadata(self) -> Dict[str, str]:
        """
        Get current encryption metadata

        Returns:
            Dictionary with algorithm and version
        """
        return {"algorithm": self.default_algorithm, "version": self.version}

    def set_algorithm(self, algorithm: str) -> None:
        """
        Set the default encryption algorithm

        Args:
            algorithm: Algorithm name to set as default
        """
        if algorithm not in ENCRYPTION_CONFIG["SUPPORTED_ALGORITHMS"]:
            raise ValueError(f"Unsupported algorithm: {algorithm}")

        if algorithm not in self.algorithms:
            raise ValueError(f"Algorithm not implemented: {algorithm}")

        self.default_algorithm = algorithm
        logger.info(f"Default encryption algorithm set to: {algorithm}")


# Global encryption service instance
encryption_service = EncryptionService()
