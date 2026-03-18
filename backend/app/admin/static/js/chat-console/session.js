export function normalizeVaultCandidate(raw) {
  if (!raw || typeof raw !== 'object') {
    return null;
  }
  if (typeof raw.account_id !== 'string' || !raw.account_id) {
    return null;
  }
  if (typeof raw.identifier !== 'string' || !raw.identifier) {
    return null;
  }
  if (typeof raw.user_qiao_id !== 'string' || !raw.user_qiao_id) {
    return null;
  }
  if (typeof raw.refresh_token !== 'string' || !raw.refresh_token) {
    return null;
  }
  if (typeof raw.device_id !== 'string' || !raw.device_id) {
    return null;
  }

  return {
    account_id: raw.account_id,
    user_qiao_id: raw.user_qiao_id,
    identifier: raw.identifier,
    device_id: raw.device_id,
    refresh_token: raw.refresh_token,
    access_token: typeof raw.access_token === 'string' ? raw.access_token : '',
    expires_at_ms: Number.isFinite(raw.expires_at_ms) ? raw.expires_at_ms : 0,
    last_used_at_ms: Number.isFinite(raw.last_used_at_ms) ? raw.last_used_at_ms : 0,
    user: raw.user && typeof raw.user === 'object' ? raw.user : {},
  };
}

export function normalizeVaultAccounts(rawAccounts, maxAccounts) {
  const accounts = Array.isArray(rawAccounts) ? rawAccounts.map(normalizeVaultCandidate).filter(Boolean) : [];

  const uniqueMap = new Map();
  for (const account of accounts) {
    uniqueMap.set(account.account_id, account);
  }
  return [...uniqueMap.values()]
    .sort((a, b) => (b.last_used_at_ms || 0) - (a.last_used_at_ms || 0))
    .slice(0, maxAccounts);
}

export function resolveActiveAccountId(activeAccountId, normalizedAccounts) {
  if (typeof activeAccountId === 'string' && normalizedAccounts.some((item) => item.account_id === activeAccountId)) {
    return activeAccountId;
  }
  return normalizedAccounts[0] ? normalizedAccounts[0].account_id : null;
}

function isAllowedPlaintextVaultHost(hostname) {
  const normalized = String(hostname || '')
    .trim()
    .toLowerCase();
  if (!normalized) {
    return false;
  }
  if (normalized === 'localhost' || normalized === '::1' || normalized === '[::1]' || normalized === '0.0.0.0') {
    return true;
  }
  if (/^127\.\d{1,3}\.\d{1,3}\.\d{1,3}$/.test(normalized)) {
    return true;
  }

  const ipv4Match = normalized.match(/^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/);
  if (!ipv4Match) {
    return false;
  }

  const octets = ipv4Match.slice(1).map(Number);
  if (octets.some((item) => item < 0 || item > 255)) {
    return false;
  }
  if (octets[0] === 10) {
    return true;
  }
  if (octets[0] === 192 && octets[1] === 168) {
    return true;
  }
  if (octets[0] === 172 && octets[1] >= 16 && octets[1] <= 31) {
    return true;
  }
  return false;
}

export function createVaultCrypto({ masterKey, saltKey, bytesToBase64, base64ToBytes, safeJsonParse }) {
  const supportsSecureVaultPersistence =
    typeof window !== 'undefined' &&
    !!window.crypto &&
    typeof window.crypto.getRandomValues === 'function' &&
    !!window.crypto.subtle &&
    typeof window.crypto.subtle.importKey === 'function' &&
    typeof window.crypto.subtle.deriveKey === 'function' &&
    typeof window.crypto.subtle.encrypt === 'function' &&
    typeof window.crypto.subtle.decrypt === 'function';
  const allowsPlaintextVaultPersistence =
    typeof window !== 'undefined' &&
    !supportsSecureVaultPersistence &&
    isAllowedPlaintextVaultHost(window.location && window.location.hostname);
  const vaultPersistenceMode = supportsSecureVaultPersistence
    ? 'encrypted'
    : allowsPlaintextVaultPersistence
      ? 'plain'
      : 'memory';
  let vaultKeyPromise = null;

  function ensureVaultMasterSecret() {
    let secret = localStorage.getItem(masterKey);
    if (!secret) {
      const bytes = new Uint8Array(32);
      crypto.getRandomValues(bytes);
      secret = bytesToBase64(bytes);
      localStorage.setItem(masterKey, secret);
    }
    return secret;
  }

  function ensureVaultSalt() {
    let salt = localStorage.getItem(saltKey);
    if (!salt) {
      const bytes = new Uint8Array(16);
      crypto.getRandomValues(bytes);
      salt = bytesToBase64(bytes);
      localStorage.setItem(saltKey, salt);
    }
    return salt;
  }

  async function getVaultCryptoKey() {
    if (!supportsSecureVaultPersistence) {
      throw new Error('SECURE_VAULT_PERSISTENCE_UNAVAILABLE');
    }
    if (vaultKeyPromise) {
      return vaultKeyPromise;
    }
    const secret = ensureVaultMasterSecret();
    const salt = ensureVaultSalt();
    vaultKeyPromise = (async () => {
      const encoder = new window.TextEncoder();
      const imported = await crypto.subtle.importKey('raw', encoder.encode(secret), 'PBKDF2', false, ['deriveKey']);
      return crypto.subtle.deriveKey(
        {
          name: 'PBKDF2',
          salt: base64ToBytes(salt),
          iterations: 120000,
          hash: 'SHA-256',
        },
        imported,
        { name: 'AES-GCM', length: 256 },
        false,
        ['encrypt', 'decrypt']
      );
    })();
    return vaultKeyPromise;
  }

  async function encryptVaultPayload(obj) {
    if (vaultPersistenceMode === 'plain') {
      return {
        v: 0,
        mode: 'plain',
        data: obj,
      };
    }
    const key = await getVaultCryptoKey();
    const encoder = new window.TextEncoder();
    const iv = new Uint8Array(12);
    crypto.getRandomValues(iv);
    const plain = encoder.encode(JSON.stringify(obj));
    const cipher = await crypto.subtle.encrypt({ name: 'AES-GCM', iv }, key, plain);
    return {
      v: 1,
      iv: bytesToBase64(iv),
      data: bytesToBase64(new Uint8Array(cipher)),
    };
  }

  async function decryptVaultPayload(payload) {
    if (
      payload &&
      payload.v === 0 &&
      payload.mode === 'plain' &&
      vaultPersistenceMode === 'plain' &&
      payload.data &&
      typeof payload.data === 'object'
    ) {
      return payload.data;
    }
    if (!payload || payload.v !== 1 || typeof payload.iv !== 'string' || typeof payload.data !== 'string') {
      throw new Error('INVALID_VAULT_PAYLOAD');
    }
    const key = await getVaultCryptoKey();
    const decoder = new window.TextDecoder();
    const plainBuffer = await crypto.subtle.decrypt(
      { name: 'AES-GCM', iv: base64ToBytes(payload.iv) },
      key,
      base64ToBytes(payload.data)
    );
    return safeJsonParse(decoder.decode(plainBuffer), null);
  }

  return Object.freeze({
    vaultPersistenceMode,
    encryptVaultPayload,
    decryptVaultPayload,
  });
}
