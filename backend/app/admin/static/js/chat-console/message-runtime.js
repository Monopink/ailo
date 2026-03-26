export function createMessageRuntimeController({
  el,
  state,
  api,
  STAGE,
  ackFlushDelayMs,
  ackBatchThreshold,
  offlinePageLimit,
  offlineMaxPages,
  localMessageLimitPerConversation,
  localMessageTtlMs,
  withDbStore,
  openLocalDb,
  getPartitionKey,
  toPersistedMessage,
  nowMs,
  normalizeCursor,
  compareCursor,
  getActiveAccount,
  getStorageAccountId,
  getMessageSortTs,
  shouldStickToBottom,
  ensureConversationStore,
  renderConversation,
  setStage,
  setStatus,
  appendLog,
  scheduleLlmLinkLookup,
  scheduleAutoLlmDetailsRefresh,
  scheduleSnapshotRefresh,
  currentEpoch,
  scheduleReconnect,
  wsSend,
  reconnectNow,
}) {
  const TYPING_START_BUFFER_MS = 1000;

  async function setStorageUnavailable(reason) {
    state.storage.available = false;
    state.storage.autoAckEnabled = false;
    if (state.storage.db) {
      try {
        state.storage.db.close();
      } catch {
        // ignore close errors
      }
      state.storage.db = null;
    }
    appendLog({ local_storage_disabled: reason });
    if (state.stage === STAGE.READY || state.stage === STAGE.RECONNECTING || state.stage === STAGE.BOOTSTRAPPING) {
      setStage(STAGE.DEGRADED, `本地存储不可用：${reason}`);
    } else {
      setStatus(`本地存储不可用：${reason}`);
    }
  }

  async function initializeLocalStorage() {
    if (!window.indexedDB) {
      await setStorageUnavailable('IndexedDB 不可用');
      return;
    }
    try {
      state.storage.db = await openLocalDb();
      state.storage.available = true;
      state.storage.autoAckEnabled = true;
      await cleanupExpiredLocalRecords();
      appendLog('local_storage_ready');
    } catch (err) {
      await setStorageUnavailable(String(err && err.message ? err.message : err));
    }
  }

  function enqueueStorageTask(task) {
    if (!state.storage.available) {
      return Promise.resolve(false);
    }
    state.storage.writeQueue = state.storage.writeQueue
      .then(() => task())
      .catch(async (err) => {
        await setStorageUnavailable(String(err && err.message ? err.message : err));
        return false;
      });
    return state.storage.writeQueue;
  }

  async function waitForStorageIdle() {
    try {
      await state.storage.writeQueue;
    } catch {
      // ignore queue errors
    }
  }

  async function cleanupExpiredLocalRecords() {
    if (!state.storage.available) return;
    const now = nowMs();
    await withDbStore('readwrite', (store) => {
      const idx = store.index('by_expiry');
      const range = window.IDBKeyRange.upperBound(now);
      const req = idx.openCursor(range);
      req.onsuccess = () => {
        const cursor = req.result;
        if (!cursor) return;
        cursor.delete();
        cursor.continue();
      };
    });
  }

  async function persistMessage(msg) {
    if (!state.storage.available) return false;
    const accountId = getStorageAccountId();
    if (!accountId || !msg || !msg.conversation_id) return false;
    const messageId = msg.msg_id_server || msg.id;
    if (!messageId) return false;
    const partitionKey = getPartitionKey(accountId, msg.conversation_id);
    const record = {
      pk: `${partitionKey}::${messageId}`,
      account_id: accountId,
      account_conversation_key: partitionKey,
      sent_at_ms: Number(getMessageSortTs(msg) || nowMs()),
      expires_at_ms: nowMs() + localMessageTtlMs,
      payload: toPersistedMessage(msg),
    };

    return enqueueStorageTask(async () => {
      await withDbStore('readwrite', (store) => {
        store.put(record);
      });
      await pruneLocalPartition(partitionKey);
      return true;
    });
  }

  async function pruneLocalPartition(partitionKey) {
    if (!state.storage.available) return;
    const now = nowMs();
    const records = [];
    await withDbStore('readwrite', (store, tx, resolve, reject) => {
      const idx = store.index('by_partition_sent');
      const range = window.IDBKeyRange.bound(
        [partitionKey, Number.MIN_SAFE_INTEGER],
        [partitionKey, Number.MAX_SAFE_INTEGER]
      );
      const req = idx.openCursor(range);
      req.onsuccess = () => {
        const cursor = req.result;
        if (!cursor) {
          const valid = records.filter((row) => row.expires_at_ms > now);
          const overflow = valid.length - localMessageLimitPerConversation;
          if (overflow > 0) {
            for (let i = 0; i < overflow; i += 1) {
              store.delete(valid[i].key);
            }
          }
          for (const row of records) {
            if (row.expires_at_ms <= now) {
              store.delete(row.key);
            }
          }
          resolve(true);
          return;
        }
        records.push({
          key: cursor.primaryKey,
          expires_at_ms: Number(cursor.value && cursor.value.expires_at_ms ? cursor.value.expires_at_ms : 0),
        });
        cursor.continue();
      };
      req.onerror = () => reject(req.error || tx.error || new Error('IDB_PRUNE_FAILED'));
    });
  }

  async function hydrateConversationFromLocal(conversationId, { forceBottom = false } = {}) {
    if (!state.storage.available || !conversationId) return;
    const accountId = getStorageAccountId();
    if (!accountId) return;
    const partitionKey = getPartitionKey(accountId, conversationId);
    if (state.storage.loadedKeys.has(partitionKey)) {
      return;
    }
    state.storage.loadedKeys.add(partitionKey);

    const rows = [];
    await withDbStore('readonly', (store, tx, resolve, reject) => {
      const idx = store.index('by_partition_sent');
      const range = window.IDBKeyRange.bound(
        [partitionKey, Number.MIN_SAFE_INTEGER],
        [partitionKey, Number.MAX_SAFE_INTEGER]
      );
      const req = idx.openCursor(range);
      req.onsuccess = () => {
        const cursor = req.result;
        if (!cursor) {
          resolve(true);
          return;
        }
        rows.push(cursor.value);
        cursor.continue();
      };
      req.onerror = () => reject(req.error || tx.error || new Error('IDB_READ_FAILED'));
    });

    const store = ensureConversationStore(conversationId);
    const now = nowMs();
    for (const row of rows) {
      if (!row || row.expires_at_ms <= now || !row.payload) {
        continue;
      }
      const msg = row.payload;
      const msgId = msg.msg_id_server || msg.id;
      if (!msgId) {
        continue;
      }
      if (store.byId.has(msgId)) {
        continue;
      }
      store.byId.set(msgId, msg);
      store.order.push(msgId);
      if (msg.msg_id_server && msg.llm_request_id) {
        state.llmLinkByMsgId.set(msg.msg_id_server, String(msg.llm_request_id));
      }
    }
    if (state.selectedConversationId === conversationId) {
      renderConversation(conversationId, forceBottom);
      scheduleLlmLinkLookup();
      scheduleAutoLlmDetailsRefresh();
    }
  }

  async function clearLocalMessagesForActiveAccount() {
    if (!state.storage.available) {
      setStatus('本地存储不可用。');
      return;
    }
    const accountId = getStorageAccountId();
    if (!accountId) {
      setStatus('当前无活跃账号。');
      return;
    }
    await withDbStore('readwrite', (store, tx, resolve, reject) => {
      const idx = store.index('by_account');
      const req = idx.openCursor(window.IDBKeyRange.only(accountId));
      req.onsuccess = () => {
        const cursor = req.result;
        if (!cursor) {
          resolve(true);
          return;
        }
        cursor.delete();
        cursor.continue();
      };
      req.onerror = () => reject(req.error || tx.error || new Error('IDB_CLEAR_FAILED'));
    });
    state.storage.loadedKeys.clear();
    state.messagesByConversation.clear();
    state.llmLinkByMsgId.clear();
    state.ack.candidate = null;
    state.ack.lastAcked = null;
    state.ack.stagedCount = 0;
    if (state.selectedConversationId) {
      renderConversation(state.selectedConversationId, true);
    } else {
      el.messageList.innerHTML = '';
    }
    setStatus('本地消息已清空。');
  }

  function considerAckCandidate(msgIdServer, sentAtMs) {
    if (!state.storage.autoAckEnabled) {
      return;
    }
    if (!msgIdServer) {
      return;
    }
    const next = normalizeCursor(msgIdServer, sentAtMs);
    if (compareCursor(next, state.ack.candidate) > 0) {
      state.ack.candidate = next;
      state.ack.stagedCount += 1;
      if (state.ack.stagedCount >= ackBatchThreshold) {
        scheduleAckFlush('batch-threshold', true);
      } else {
        scheduleAckFlush('message-ingest', false);
      }
    }
  }

  function scheduleAckFlush(reason, immediate) {
    if (state.ack.flushTimer) {
      window.clearTimeout(state.ack.flushTimer);
      state.ack.flushTimer = null;
    }
    const delay = immediate ? 0 : ackFlushDelayMs;
    state.ack.flushTimer = window.setTimeout(() => {
      state.ack.flushTimer = null;
      void flushAck(reason);
    }, delay);
  }

  async function flushAck(reason) {
    if (!state.storage.autoAckEnabled) {
      return;
    }
    if (state.ack.inFlight) {
      return;
    }
    if (state.offlineInFlight) {
      return;
    }
    const account = getActiveAccount();
    if (!account) {
      return;
    }
    if (!state.ack.candidate || !state.ack.candidate.msg_id_server) {
      return;
    }
    if (compareCursor(state.ack.candidate, state.ack.lastAcked) <= 0) {
      return;
    }

    state.ack.inFlight = true;
    try {
      const payload = {
        device_id: account.device_id,
        last_ack_msg_id: state.ack.candidate.msg_id_server,
      };
      await api('/api/v1/messages/ack', { method: 'POST', body: payload, auth: true });
      state.ack.lastAcked = state.ack.candidate;
      state.ack.stagedCount = 0;
      appendLog({ ack_auto_ok: { reason, last_ack_msg_id: payload.last_ack_msg_id } });
    } catch (err) {
      appendLog({ ack_auto_failed: String(err && err.message ? err.message : err) });
    } finally {
      state.ack.inFlight = false;
    }
  }

  function markPendingStatus(pendingId, conversationId, status) {
    const store = ensureConversationStore(conversationId);
    const msg = store.byId.get(pendingId);
    if (!msg) {
      return;
    }
    msg.status = status;
    if (state.selectedConversationId === conversationId) {
      renderConversation(conversationId);
    }
  }

  function promotePendingMessage(pendingId, conversationId, msgIdClient, msgIdServer, sentAtMs) {
    const store = ensureConversationStore(conversationId);
    const pending = store.byId.get(pendingId);
    if (!pending) {
      return;
    }

    const existing = store.byId.get(msgIdServer);
    if (!existing) {
      const promoted = {
        ...pending,
        id: msgIdServer,
        msg_id_server: msgIdServer,
        msg_id_client: msgIdClient || pending.msg_id_client || null,
        llm_request_id: state.llmLinkByMsgId.get(msgIdServer) || null,
        sent_at_ms: sentAtMs || pending.sent_at_ms || nowMs(),
        status: '',
        pending: false,
      };

      const idx = store.order.indexOf(pendingId);
      if (idx >= 0) {
        store.order[idx] = msgIdServer;
      }
      store.byId.delete(pendingId);
      store.byId.set(msgIdServer, promoted);
      el.ackMsgId.value = promoted.msg_id_server;
      void persistMessage(promoted).then((stored) => {
        if (stored) {
          considerAckCandidate(promoted.msg_id_server, promoted.sent_at_ms);
        }
      });
      scheduleLlmLinkLookup();
    } else {
      const idx = store.order.indexOf(pendingId);
      if (idx >= 0) {
        store.order.splice(idx, 1);
      }
      store.byId.delete(pendingId);
    }

    if (msgIdClient) {
      state.pendingByClientId.delete(msgIdClient);
    }
    if (state.selectedConversationId === conversationId) {
      renderConversation(conversationId, true);
    }
  }

  function createPendingMessage(conversationId, content, msgIdClient) {
    const pendingId = `pending_${nowMs()}_${Math.random().toString(16).slice(2)}`;
    const store = ensureConversationStore(conversationId);
    const msg = {
      id: pendingId,
      msg_id_server: null,
      msg_id_client: msgIdClient,
      llm_request_id: null,
      message_type: 1,
      conversation_id: conversationId,
      direction: 'out',
      content,
      sent_at_ms: nowMs(),
      client_sent_time_ms: nowMs(),
      status: '发送中...',
      pending: true,
      metadata: {},
    };
    store.byId.set(pendingId, msg);
    store.order.push(pendingId);

    if (state.selectedConversationId === conversationId) {
      renderConversation(conversationId, true);
    }
    return pendingId;
  }

  function ingestTimelineMessage(message, source) {
    if (!message || typeof message !== 'object') {
      return;
    }
    if (!message.conversation_id || !message.msg_id_server) {
      return;
    }

    const conversationId = message.conversation_id;
    const msgIdServer = message.msg_id_server;
    const msgIdClient = typeof message.msg_id_client === 'string' ? message.msg_id_client : null;
    const messageType = Number(message.message_type || 0);
    const metadata = message.metadata && typeof message.metadata === 'object' ? message.metadata : {};
    const incomingLlmRequestId =
      message.llm_request_id === null || message.llm_request_id === undefined ? null : String(message.llm_request_id);
    if (incomingLlmRequestId) {
      state.llmLinkByMsgId.set(msgIdServer, incomingLlmRequestId);
    }
    const store = ensureConversationStore(conversationId);

    if (msgIdClient && state.pendingByClientId.has(msgIdClient)) {
      const pendingId = state.pendingByClientId.get(msgIdClient);
      promotePendingMessage(pendingId, conversationId, msgIdClient, msgIdServer, Number(message.sent_time_ms || 0));
      state.pendingByClientId.delete(msgIdClient);
      return;
    }

    if (store.byId.has(msgIdServer)) {
      const existing = store.byId.get(msgIdServer);
      existing.content = message.content || existing.content || '';
      existing.sent_at_ms = Number(message.sent_time_ms || existing.sent_at_ms || 0);
      if (existing.direction === 'out') {
        existing.client_sent_time_ms = Number(message.client_sent_time_ms || existing.client_sent_time_ms || 0);
      } else {
        existing.client_sent_time_ms = 0;
      }
      existing.llm_request_id =
        incomingLlmRequestId || state.llmLinkByMsgId.get(msgIdServer) || existing.llm_request_id || null;
      existing.message_type = messageType || existing.message_type || 1;
      existing.metadata = metadata || existing.metadata || {};
      existing.status = '';
      existing.pending = false;
      if (state.selectedConversationId === conversationId) {
        renderConversation(conversationId);
      }
      el.ackMsgId.value = msgIdServer;
      void persistMessage(existing).then((stored) => {
        if (stored) {
          considerAckCandidate(msgIdServer, existing.sent_at_ms);
        }
      });
      scheduleLlmLinkLookup();
      if (source === 'ws-event' && existing.direction === 'in' && state.selectedConversationId === conversationId) {
        scheduleSnapshotRefresh();
      }
      scheduleAutoLlmDetailsRefresh();
      return;
    }

    const account = getActiveAccount();
    const selfQiaoId = account ? account.user_qiao_id : null;
    const direction = selfQiaoId && message.from_qiao_id === selfQiaoId ? 'out' : 'in';

    const msg = {
      id: msgIdServer,
      msg_id_server: msgIdServer,
      msg_id_client: msgIdClient,
      llm_request_id: incomingLlmRequestId || state.llmLinkByMsgId.get(msgIdServer) || null,
      message_type: messageType || 1,
      conversation_id: conversationId,
      direction,
      content: message.content || '',
      sent_at_ms: Number(message.sent_time_ms || 0),
      client_sent_time_ms: direction === 'out' ? Number(message.client_sent_time_ms || 0) : 0,
      status: '',
      pending: false,
      metadata,
    };

    store.byId.set(msgIdServer, msg);
    store.order.push(msgIdServer);

    if (state.selectedConversationId === conversationId) {
      const keepBottom = shouldStickToBottom();
      renderConversation(conversationId, keepBottom);
    }

    el.ackMsgId.value = msgIdServer;
    void persistMessage(msg).then((stored) => {
      if (stored) {
        considerAckCandidate(msgIdServer, msg.sent_at_ms);
      }
    });
    scheduleLlmLinkLookup();
    if (source === 'ws-event' && direction === 'in' && state.selectedConversationId === conversationId) {
      scheduleSnapshotRefresh();
    }
    scheduleAutoLlmDetailsRefresh();
  }

  async function pullOffline({ reason = 'manual', silent = false } = {}) {
    const account = getActiveAccount();
    if (!account) {
      throw new Error('AUTH_REQUIRED');
    }
    if (state.offlineInFlight) {
      return 0;
    }

    state.offlineInFlight = true;
    let total = 0;
    let cursor = null;
    let hasMore = true;
    let page = 0;

    try {
      while (hasMore && page < offlineMaxPages) {
        page += 1;
        const q = new window.URLSearchParams();
        q.set('device_id', account.device_id);
        q.set('limit', String(offlinePageLimit));
        if (cursor) {
          q.set('cursor', cursor);
        }

        const res = await api(`/api/v1/messages/offline?${q.toString()}`, { method: 'GET', auth: true });
        const messages = res && Array.isArray(res.messages) ? res.messages : [];

        for (const msg of messages) {
          ingestTimelineMessage(msg, 'offline');
          total += 1;
        }

        hasMore = Boolean(res && res.has_more);
        cursor = res && res.next_cursor ? String(res.next_cursor) : null;
      }

      if (hasMore) {
        appendLog({ offline_truncated: { reason, pages: offlineMaxPages } });
      }
      await waitForStorageIdle();
      await flushAck('offline-finished');
      scheduleLlmLinkLookup();
      if (total > 0) {
        scheduleSnapshotRefresh();
        scheduleAutoLlmDetailsRefresh();
      }
      if (!silent) {
        setStatus(`离线消息同步完成：${total}`);
      }
      appendLog({ offline_done: { reason, total } });
      return total;
    } finally {
      state.offlineInFlight = false;
    }
  }

  async function sendManualAck() {
    const account = getActiveAccount();
    if (!account) {
      setStatus('请先登录。');
      return;
    }
    const msgId = (el.ackMsgId.value || '').trim();
    if (!msgId) {
      setStatus('请输入 msg_id_server。');
      return;
    }
    try {
      await api('/api/v1/messages/ack', {
        method: 'POST',
        auth: true,
        body: { device_id: account.device_id, last_ack_msg_id: msgId },
      });
      setStatus('手动 ACK 已发送。');
      appendLog({ ack_manual_ok: msgId });
      state.ack.lastAcked = normalizeCursor(msgId, state.ack.candidate ? state.ack.candidate.sent_at_ms : 0);
    } catch (err) {
      setStatus('手动 ACK 发送失败。');
      appendLog({ ack_manual_failed: String(err && err.message ? err.message : err) });
    }
  }

  function sendTyping(stateValue, conversationId = state.selectedConversationId) {
    if (!state.wsAuthed || !conversationId) {
      return false;
    }
    const msgIdClient = `typing_${nowMs()}_${Math.random().toString(16).slice(2)}`;
    try {
      wsSend(
        'typing',
        {
          msg_id_client: msgIdClient,
          conversation_id: conversationId,
          typing_state: stateValue,
          supports_typing: true,
          client_sent_time_ms: nowMs(),
        },
        'typing'
      );
      appendLog({ self_typing_emit: stateValue, conversation_id: conversationId });
      return true;
    } catch (err) {
      appendLog({ typing_send_failed: String(err && err.message ? err.message : err) });
      return false;
    }
  }

  function cancelTypingStartBuffer() {
    if (!state.typingStartBufferTimer) {
      return;
    }
    window.clearTimeout(state.typingStartBufferTimer);
    state.typingStartBufferTimer = null;
  }

  function scheduleTypingStartIfNeeded() {
    if (!state.wsAuthed || !state.selectedConversationId) {
      return;
    }
    const conversationId = state.selectedConversationId;
    if (state.typingActive && state.typingActiveConversationId === conversationId) {
      return;
    }
    if (state.typingStartBufferTimer) {
      return;
    }
    state.typingStartBufferTimer = window.setTimeout(() => {
      state.typingStartBufferTimer = null;
      if (!state.wsAuthed || state.selectedConversationId !== conversationId) {
        return;
      }
      if (state.typingActive && state.typingActiveConversationId === conversationId) {
        return;
      }
      const sent = sendTyping('start', conversationId);
      if (!sent) {
        return;
      }
      state.typingActive = true;
      state.typingActiveConversationId = conversationId;
    }, TYPING_START_BUFFER_MS);
  }

  function stopTypingIfNeeded({ emitEnd = true } = {}) {
    cancelTypingStartBuffer();
    const activeConversationId = state.typingActiveConversationId;
    if (!state.typingActive || !activeConversationId) {
      state.typingActive = false;
      state.typingActiveConversationId = null;
      return;
    }
    if (emitEnd) {
      sendTyping('end', activeConversationId);
    }
    state.typingActive = false;
    state.typingActiveConversationId = null;
  }

  async function sendMessage() {
    const account = getActiveAccount();
    if (!account) {
      setStatus('请先登录。');
      return;
    }

    const conversationId = state.selectedConversationId;
    if (!conversationId) {
      setStatus('请先选择聊天。');
      return;
    }

    const content = (el.messageInput.value || '').replace(/\r/g, '').trim();
    if (!content) {
      return;
    }

    if (!state.wsAuthed) {
      setStatus('连接已断开，消息未发送。');
      return;
    }

    if (state.typingHintTimer) {
      window.clearTimeout(state.typingHintTimer);
      state.typingHintTimer = null;
    }
    el.typingHint.textContent = '';
    state.isMessageInputComposing = false;

    stopTypingIfNeeded({ emitEnd: false });

    const msgIdClient = `client_${nowMs()}_${Math.random().toString(16).slice(2)}`;
    const pendingId = createPendingMessage(conversationId, content, msgIdClient);
    el.messageInput.value = '';

    try {
      const frameId = wsSend(
        'send_message',
        {
          msg_id_client: msgIdClient,
          conversation_id: conversationId,
          content,
          supports_typing: true,
          client_sent_time_ms: nowMs(),
        },
        'send'
      );
      state.pendingByFrameId.set(frameId, {
        pending_id: pendingId,
        conversation_id: conversationId,
        msg_id_client: msgIdClient,
      });
      state.pendingByClientId.set(msgIdClient, pendingId);
      setStatus('发送中...');
    } catch (err) {
      markPendingStatus(pendingId, conversationId, '失败');
      appendLog({ send_failed: String(err && err.message ? err.message : err) });
      setStatus('发送失败。');
      scheduleReconnect('send-failed', currentEpoch());
    }
  }

  async function reconnectButtonAction() {
    const epoch = currentEpoch();
    if (!getActiveAccount()) {
      return;
    }
    if (state.reconnectTimer) {
      window.clearTimeout(state.reconnectTimer);
      state.reconnectTimer = null;
    }
    state.reconnectAttempt = 0;
    setStage(STAGE.RECONNECTING, '手动重连中...');
    await reconnectNow(epoch, 'manual');
  }

  return Object.freeze({
    setStorageUnavailable,
    initializeLocalStorage,
    enqueueStorageTask,
    waitForStorageIdle,
    cleanupExpiredLocalRecords,
    persistMessage,
    pruneLocalPartition,
    hydrateConversationFromLocal,
    clearLocalMessagesForActiveAccount,
    considerAckCandidate,
    scheduleAckFlush,
    flushAck,
    markPendingStatus,
    promotePendingMessage,
    createPendingMessage,
    ingestTimelineMessage,
    pullOffline,
    sendManualAck,
    sendTyping,
    scheduleTypingStartIfNeeded,
    cancelTypingStartBuffer,
    stopTypingIfNeeded,
    sendMessage,
    reconnectButtonAction,
  });
}
