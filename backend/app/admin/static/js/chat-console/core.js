export function createDeferred() {
  let resolve;
  let reject;
  const promise = new Promise((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

export function randFrameId(prefix) {
  const bytes = new Uint8Array(12);
  crypto.getRandomValues(bytes);
  let binary = '';
  for (const b of bytes) {
    binary += String.fromCharCode(b);
  }
  const base64 = btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '');
  return `${prefix}_${base64}`;
}

export function bytesToBase64(bytes) {
  let binary = '';
  for (const b of bytes) {
    binary += String.fromCharCode(b);
  }
  return btoa(binary);
}

export function base64ToBytes(base64) {
  const binary = window.atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

export function safeJsonParse(text, fallback) {
  try {
    return JSON.parse(text);
  } catch {
    return fallback;
  }
}

export function nowMs() {
  return Date.now();
}

export function makeDeviceId() {
  return crypto.randomUUID();
}

export function makeAccountId(userQiaoId, identifier) {
  return `${userQiaoId || 'unknown'}::${(identifier || '').trim().toLowerCase()}`;
}

export function extractErrorMessage(body, res) {
  if (body && typeof body === 'object') {
    if (typeof body.message === 'string' && body.message) {
      return body.message;
    }
    if (typeof body.detail === 'string' && body.detail) {
      return body.detail;
    }
    if (body.detail && typeof body.detail === 'object' && typeof body.detail.message === 'string') {
      return body.detail.message;
    }
  }
  return `${res.status} ${res.statusText}`;
}

export function createApiClient({ getActiveAccount, ensureValidAccessToken, refreshAccessToken }) {
  return async function api(path, { method = 'GET', body = null, auth = true, retryOn401 = true } = {}) {
    const headers = {};
    if (body !== null) {
      headers['Content-Type'] = 'application/json';
    }

    const account = getActiveAccount();
    if (auth) {
      if (!account) {
        throw new Error('AUTH_REQUIRED');
      }
      await ensureValidAccessToken(account, { force: false });
      headers.Authorization = `Bearer ${account.access_token}`;
    }

    const res = await fetch(path, {
      method,
      headers,
      body: body !== null ? JSON.stringify(body) : null,
    });

    let json = null;
    try {
      json = await res.json();
    } catch {
      json = null;
    }

    if (res.status === 401 && auth && retryOn401) {
      if (!account) {
        throw new Error('Session expired');
      }
      await refreshAccessToken(account);
      return api(path, { method, body, auth, retryOn401: false });
    }

    if (!res.ok) {
      throw new Error(extractErrorMessage(json, res));
    }
    return json;
  };
}

export function parseWsFrame(raw) {
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function normalizeCursor(msgId, sentAtMs) {
  const numericPart = typeof msgId === 'string' ? msgId.split('_').pop() : null;
  const msgNumeric = numericPart && /^\d+$/.test(numericPart) ? BigInt(numericPart) : null;
  return {
    msg_id_server: msgId,
    sent_at_ms: Number(sentAtMs || 0),
    msg_numeric: msgNumeric,
  };
}

export function compareCursor(a, b) {
  if (!a && !b) return 0;
  if (!a) return -1;
  if (!b) return 1;

  if (a.sent_at_ms !== b.sent_at_ms) {
    return a.sent_at_ms - b.sent_at_ms;
  }

  if (a.msg_numeric !== null && b.msg_numeric !== null) {
    if (a.msg_numeric < b.msg_numeric) return -1;
    if (a.msg_numeric > b.msg_numeric) return 1;
    return 0;
  }

  return String(a.msg_id_server).localeCompare(String(b.msg_id_server));
}
