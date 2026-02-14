export function getPartitionKey(accountId, conversationId) {
  return `${accountId}::${conversationId}`;
}

export function withDbStore(db, storeName, mode, executor) {
  return new Promise((resolve, reject) => {
    if (!db) {
      reject(new Error('IDB_NOT_READY'));
      return;
    }
    const tx = db.transaction(storeName, mode);
    const store = tx.objectStore(storeName);
    let settled = false;
    tx.oncomplete = () => {
      if (!settled) {
        settled = true;
        resolve(true);
      }
    };
    tx.onerror = () => {
      if (!settled) {
        settled = true;
        reject(tx.error || new Error('IDB_TX_FAILED'));
      }
    };
    tx.onabort = () => {
      if (!settled) {
        settled = true;
        reject(tx.error || new Error('IDB_TX_ABORTED'));
      }
    };
    executor(store, tx, resolve, reject);
  });
}

export function openLocalDb({ dbName, dbVersion, storeName }) {
  return new Promise((resolve, reject) => {
    const req = window.indexedDB.open(dbName, dbVersion);
    req.onupgradeneeded = () => {
      const db = req.result;
      let store;
      if (!db.objectStoreNames.contains(storeName)) {
        store = db.createObjectStore(storeName, { keyPath: 'pk' });
      } else {
        store = req.transaction.objectStore(storeName);
      }
      if (!store.indexNames.contains('by_partition_sent')) {
        store.createIndex('by_partition_sent', ['account_conversation_key', 'sent_at_ms'], {
          unique: false,
        });
      }
      if (!store.indexNames.contains('by_account')) {
        store.createIndex('by_account', 'account_id', { unique: false });
      }
      if (!store.indexNames.contains('by_expiry')) {
        store.createIndex('by_expiry', 'expires_at_ms', { unique: false });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error || new Error('IDB_OPEN_FAILED'));
  });
}

export function toPersistedMessage(msg) {
  return {
    id: msg.id,
    msg_id_server: msg.msg_id_server || null,
    msg_id_client: msg.msg_id_client || null,
    llm_request_id: msg.llm_request_id || null,
    conversation_id: msg.conversation_id,
    direction: msg.direction || 'in',
    content: msg.content || '',
    sent_at_ms: Number(msg.sent_at_ms || 0),
    client_sent_time_ms: msg.direction === 'out' ? Number(msg.client_sent_time_ms || 0) : 0,
    status: msg.status || '',
    pending: Boolean(msg.pending),
  };
}
