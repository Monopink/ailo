/**
 * Message encryption wrapper for handling encrypted message format
 * Provides high-level interface for encrypting/decrypting message objects
 */

import { encryptionService } from './encryptionService'
import { ENCRYPTION_CONFIG } from '../../config/encryption'
import { EncryptionType, EncryptionVersion } from '../messaging/types'

class MessageEncryption {
  constructor() {
    this.encryptionService = encryptionService
  }

  /**
   * Encrypt a message object
   * @param {object} message - Original message object
   * @returns {object} - Encrypted message object with encryption metadata
   */
  encryptMessage(message) {
    if (!message || typeof message !== 'object') {
      throw new Error('Message must be a valid object')
    }

    if (!message.content) {
      // No content to encrypt, return as-is
      return message
    }

    try {
      // Create a copy to avoid mutating original
      const encryptedMessage = { ...message }

      // Encrypt the content
      encryptedMessage.content = this.encryptionService.encrypt(message.content)

      // Add encryption metadata using numeric codes
      encryptedMessage.encryption = EncryptionType.BASE64
      encryptedMessage.enc_version = EncryptionVersion.V1

      // Log operation if debugging is enabled
      if (ENCRYPTION_CONFIG.DEBUG.LOG_OPERATIONS) {
        console.log('Message encrypted:', {
          encryption: encryptedMessage.encryption,
          enc_version: encryptedMessage.enc_version,
          originalLength: message.content.length,
          encryptedLength: encryptedMessage.content.length
        })
      }

      return encryptedMessage
    } catch (error) {
      console.error('Failed to encrypt message:', error)
      throw new Error(`Message encryption failed: ${error.message}`)
    }
  }

  /**
   * Decrypt a message object
   * @param {object} encryptedMessage - Encrypted message object
   * @returns {object} - Decrypted message object without encryption metadata
   */
  decryptMessage(encryptedMessage) {
    if (!encryptedMessage || typeof encryptedMessage !== 'object') {
      throw new Error('Encrypted message must be a valid object')
    }

    // Check if message is actually encrypted (using new format)
    if (!this.isMessageEncrypted(encryptedMessage)) {
      // Not encrypted, return as-is (backward compatibility)
      console.log('🔓 [MessageEncryption] Message is not encrypted, returning as-is')
      return encryptedMessage
    }

    console.log('🔓 [MessageEncryption] Message is encrypted, decrypting...')

    try {
      // Create a copy to avoid mutating original
      const decryptedMessage = { ...encryptedMessage }

      // Get encryption algorithm from metadata (numeric format)
      const encryptionType = encryptedMessage.encryption

      // Map numeric encryption type to algorithm name
      const algorithmMap = {
        [EncryptionType.BASE64]: 'base64',
        [EncryptionType.AES_256_GCM]: 'aes-256-gcm'
      }
      const algorithm = algorithmMap[encryptionType] || 'base64'

      // Decrypt the content
      decryptedMessage.content = this.encryptionService.decrypt(
        encryptedMessage.content,
        algorithm
      )

      // Remove encryption metadata from decrypted message
      delete decryptedMessage.encryption
      delete decryptedMessage.enc_version

      // Log operation if debugging is enabled
      if (ENCRYPTION_CONFIG.DEBUG.LOG_OPERATIONS) {
        console.log('Message decrypted:', {
          encryption: encryptionType,
          enc_version: encryptedMessage.enc_version,
          algorithm: algorithm,
          encryptedLength: encryptedMessage.content.length,
          decryptedLength: decryptedMessage.content.length
        })
      }

      return decryptedMessage
    } catch (error) {
      console.error('Failed to decrypt message:', error)

      // Handle decryption failure based on configuration
      if (ENCRYPTION_CONFIG.ERROR_HANDLING.FALLBACK_TO_PLAINTEXT) {
        console.warn('Falling back to encrypted content as plaintext')
        const fallbackMessage = { ...encryptedMessage }
        delete fallbackMessage.encryption
        return fallbackMessage
      }

      throw new Error(`Message decryption failed: ${error.message}`)
    }
  }

  /**
   * Check if a message is encrypted (using new numeric format)
   * @param {object} message - Message object to check
   * @returns {boolean} - True if message is encrypted
   */
  isMessageEncrypted(message) {
    return message &&
      typeof message.encryption === 'number' &&
      message.encryption > EncryptionType.NONE &&
      typeof message.enc_version === 'number'
  }

  /**
   * Get encryption status and metadata for a message
   * @param {object} message - Message object to analyze
   * @returns {object} - Encryption status and metadata
   */
  getMessageEncryptionInfo(message) {
    if (!this.isMessageEncrypted(message)) {
      return {
        encrypted: false,
        algorithm: null,
        version: null
      }
    }

    return {
      encrypted: true,
      encryption: message.encryption,
      enc_version: message.enc_version,
      algorithm: message.encryption === EncryptionType.BASE64 ? 'base64' : 'unknown'
    }
  }

  /**
   * Batch encrypt multiple messages
   * @param {array} messages - Array of message objects
   * @returns {array} - Array of encrypted message objects
   */
  encryptMessages(messages) {
    if (!Array.isArray(messages)) {
      throw new Error('Messages must be an array')
    }

    return messages.map((message, index) => {
      try {
        return this.encryptMessage(message)
      } catch (error) {
        console.error(`Failed to encrypt message at index ${index}:`, error)
        throw error
      }
    })
  }

  /**
   * Batch decrypt multiple messages
   * @param {array} encryptedMessages - Array of encrypted message objects
   * @returns {array} - Array of decrypted message objects
   */
  decryptMessages(encryptedMessages) {
    if (!Array.isArray(encryptedMessages)) {
      throw new Error('Encrypted messages must be an array')
    }

    return encryptedMessages.map((message, index) => {
      try {
        return this.decryptMessage(message)
      } catch (error) {
        console.error(`Failed to decrypt message at index ${index}:`, error)
        throw error
      }
    })
  }
}

// Export singleton instance
export const messageEncryption = new MessageEncryption()
export default MessageEncryption
