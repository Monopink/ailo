/**
 * Encryption configuration for message protection
 * Defines supported algorithms and security parameters
 */

export const ENCRYPTION_CONFIG = {
  // Current default algorithm (Base64 for phase 1)
  DEFAULT_ALGORITHM: 'base64',
  
  // Current encryption version
  VERSION: '1.0',
  
  // List of supported encryption algorithms
  SUPPORTED_ALGORITHMS: [
    'base64',
    // 'aes-256-gcm' // Future implementation
  ],
  
  // Algorithm-specific configurations
  ALGORITHMS: {
    base64: {
      name: 'Base64 Encoding',
      description: 'Simple Base64 encoding for content obfuscation',
      security_level: 'low', // Not real encryption
    },
    'aes-256-gcm': {
      name: 'AES-256-GCM',
      description: 'Advanced Encryption Standard with Galois/Counter Mode',
      security_level: 'high',
      key_size: 256,
      iv_size: 96,
    }
  },
  
  // Future key management settings
  KEY_MANAGEMENT: {
    // Key rotation interval in milliseconds (24 hours)
    ROTATION_INTERVAL: 24 * 60 * 60 * 1000,
    
    // Maximum key age in milliseconds (7 days)
    MAX_KEY_AGE: 7 * 24 * 60 * 60 * 1000,
    
    // Key derivation iterations for PBKDF2
    PBKDF2_ITERATIONS: 100000,
  },
  
  // Error handling settings
  ERROR_HANDLING: {
    // Whether to fallback to plaintext on decryption failure
    FALLBACK_TO_PLAINTEXT: false,
    
    // Maximum retry attempts for encryption/decryption
    MAX_RETRY_ATTEMPTS: 3,
  },
  
  // Development and debugging settings
  DEBUG: {
    // Log encryption/decryption operations (disable in production)
    LOG_OPERATIONS: import.meta.env.DEV,
    
    // Include encryption metadata in logs
    LOG_METADATA: import.meta.env.DEV,
  }
}

/**
 * Get algorithm configuration by name
 * @param {string} algorithmName - Name of the algorithm
 * @returns {object|null} - Algorithm configuration or null if not found
 */
export function getAlgorithmConfig(algorithmName) {
  return ENCRYPTION_CONFIG.ALGORITHMS[algorithmName] || null
}

/**
 * Check if an algorithm is supported
 * @param {string} algorithmName - Name of the algorithm to check
 * @returns {boolean} - True if algorithm is supported
 */
export function isAlgorithmSupported(algorithmName) {
  return ENCRYPTION_CONFIG.SUPPORTED_ALGORITHMS.includes(algorithmName)
}

/**
 * Get the current encryption version
 * @returns {string} - Current encryption version
 */
export function getCurrentVersion() {
  return ENCRYPTION_CONFIG.VERSION
}

/**
 * Validate encryption configuration
 * @returns {boolean} - True if configuration is valid
 */
export function validateConfig() {
  const { DEFAULT_ALGORITHM, SUPPORTED_ALGORITHMS, ALGORITHMS } = ENCRYPTION_CONFIG
  
  // Check if default algorithm is supported
  if (!SUPPORTED_ALGORITHMS.includes(DEFAULT_ALGORITHM)) {
    console.error(`Default algorithm ${DEFAULT_ALGORITHM} is not in supported algorithms list`)
    return false
  }
  
  // Check if default algorithm has configuration
  if (!ALGORITHMS[DEFAULT_ALGORITHM]) {
    console.error(`Default algorithm ${DEFAULT_ALGORITHM} has no configuration`)
    return false
  }
  
  return true
}

// Validate configuration on import
if (!validateConfig()) {
  throw new Error('Invalid encryption configuration')
}
