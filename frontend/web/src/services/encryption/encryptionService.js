/**
 * Encryption Service for message content protection
 * Currently supports Base64 encoding with future extensibility for real encryption
 */

import { ENCRYPTION_CONFIG } from '../../config/encryption'

class EncryptionService {
  constructor() {
    this.algorithm = ENCRYPTION_CONFIG.DEFAULT_ALGORITHM
    this.version = ENCRYPTION_CONFIG.VERSION
  }

  /**
   * Encrypt message content based on current algorithm
   * @param {string} content - Plain text content to encrypt
   * @returns {string} - Encrypted content
   */
  encrypt(content) {
    if (!content || typeof content !== 'string') {
      throw new Error('Content must be a non-empty string')
    }

    switch (this.algorithm) {
      case 'base64':
        return this._base64Encode(content)
      case 'aes-256-gcm':
        return this._aesEncrypt(content) // Future implementation
      default:
        throw new Error(`Unsupported encryption algorithm: ${this.algorithm}`)
    }
  }

  /**
   * Decrypt message content based on specified algorithm
   * @param {string} encryptedContent - Encrypted content to decrypt
   * @param {string} algorithm - Algorithm used for encryption
   * @returns {string} - Decrypted plain text content
   */
  decrypt(encryptedContent, algorithm = this.algorithm) {
    if (!encryptedContent || typeof encryptedContent !== 'string') {
      throw new Error('Encrypted content must be a non-empty string')
    }

    switch (algorithm) {
      case 'base64':
        return this._base64Decode(encryptedContent)
      case 'aes-256-gcm':
        return this._aesDecrypt(encryptedContent) // Future implementation
      default:
        throw new Error(`Unsupported decryption algorithm: ${algorithm}`)
    }
  }

  /**
   * Check if a message is encrypted
   * @param {object} message - Message object to check
   * @returns {boolean} - True if message is encrypted
   */
  isEncrypted(message) {
    return message && message.encryption && message.encryption.algorithm
  }

  /**
   * Get encryption metadata for message
   * @returns {object} - Encryption metadata
   */
  getEncryptionMetadata() {
    return {
      algorithm: this.algorithm,
      version: this.version
    }
  }

  /**
   * Base64 encoding implementation
   * @private
   * @param {string} content - Content to encode
   * @returns {string} - Base64 encoded content
   */
  _base64Encode(content) {
    try {
      // Handle Unicode characters properly
      return btoa(unescape(encodeURIComponent(content)))
    } catch (error) {
      throw new Error(`Base64 encoding failed: ${error.message}`)
    }
  }

  /**
   * Base64 decoding implementation
   * @private
   * @param {string} encodedContent - Base64 encoded content
   * @returns {string} - Decoded content
   */
  _base64Decode(encodedContent) {
    try {
      // Handle Unicode characters properly
      return decodeURIComponent(escape(atob(encodedContent)))
    } catch (error) {
      throw new Error(`Base64 decoding failed: ${error.message}`)
    }
  }

  /**
   * Future AES encryption implementation
   * @private
   * @param {string} content - Content to encrypt
   * @returns {string} - AES encrypted content
   */
  _aesEncrypt(content) {
    // TODO: Implement AES-256-GCM encryption
    throw new Error('AES encryption not yet implemented')
  }

  /**
   * Future AES decryption implementation
   * @private
   * @param {string} encryptedContent - AES encrypted content
   * @returns {string} - Decrypted content
   */
  _aesDecrypt(encryptedContent) {
    // TODO: Implement AES-256-GCM decryption
    throw new Error('AES decryption not yet implemented')
  }

  /**
   * Set encryption algorithm (for future use)
   * @param {string} algorithm - Algorithm to use
   */
  setAlgorithm(algorithm) {
    if (!ENCRYPTION_CONFIG.SUPPORTED_ALGORITHMS.includes(algorithm)) {
      throw new Error(`Unsupported algorithm: ${algorithm}`)
    }
    this.algorithm = algorithm
  }
}

// Export singleton instance
export const encryptionService = new EncryptionService()
export default EncryptionService
