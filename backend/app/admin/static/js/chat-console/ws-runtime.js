export function createWsRuntimeController({
  el,
  state,
  WS_BADGE,
  STAGE,
  reconnectDelaysMs,
  wsAuthTimeoutMs,
  wsPingIntervalMs,
  createDeferred,
  randFrameId,
  parseWsFrame,
  getActiveAccount,
  getSelectedContact,
  currentEpoch,
  setWsBadge,
  setAuthBadge,
  setStage,
  setStatus,
  updateControls,
  appendLog,
  contactName,
  ensureValidAccessToken,
  pullOffline,
  ingestTimelineMessage,
  promotePendingMessage,
  markPendingStatus,
}) {
  const PEER_TYPING_HINT_TIMEOUT_MS = 30000;
  const AUTH_FAILURE_MARKERS = [
    'auth_required',
    'invalid_token',
    'token_refresh_failed',
    'ws_auth_failed',
    'session expired',
    '登录失效',
    '401',
  ];

  function getErrorMessage(err) {
    return String(err && err.message ? err.message : err || '');
  }

  function isAuthFailureError(err) {
    const message = getErrorMessage(err).toLowerCase();
    return AUTH_FAILURE_MARKERS.some((marker) => message.includes(marker));
  }

  function isAuthFailureFrame(framePayload) {
    if (!framePayload || typeof framePayload !== 'object') {
      return false;
    }
    const code = typeof framePayload.code === 'string' ? framePayload.code.toLowerCase() : '';
    const message = typeof framePayload.message === 'string' ? framePayload.message.toLowerCase() : '';
    return code === 'invalid_token' || code === 'auth_required' || isAuthFailureError(message);
  }

  function clearTypingHint() {
    el.typingHint.textContent = '';
    if (state.typingHintTimer) {
      window.clearTimeout(state.typingHintTimer);
      state.typingHintTimer = null;
    }
  }

  function maybeHideTypingHintOnIncomingText(message) {
    if (!message || message.conversation_id !== state.selectedConversationId) {
      return;
    }
    if (Number(message.message_type) !== 1) {
      return;
    }
    const account = getActiveAccount();
    const contact = getSelectedContact();
    if (!account || !contact) {
      return;
    }

    const selfQiaoId = account.user_qiao_id;
    const peerQiaoId = contact.contact_qiao_id;
    if (!selfQiaoId || !peerQiaoId) {
      return;
    }

    const fromQiaoId = typeof message.from_qiao_id === 'string' ? message.from_qiao_id : '';
    const toQiaoId = typeof message.to_qiao_id === 'string' ? message.to_qiao_id : '';
    const isPeerToSelf = fromQiaoId === peerQiaoId && toQiaoId === selfQiaoId;
    const isSelfToPeer = fromQiaoId === selfQiaoId && toQiaoId === peerQiaoId;
    if (isPeerToSelf || isSelfToPeer) {
      clearTypingHint();
    }
  }

  function resetLocalTypingState() {
    if (state.typingStartBufferTimer) {
      window.clearTimeout(state.typingStartBufferTimer);
      state.typingStartBufferTimer = null;
    }
    state.isMessageInputComposing = false;
    state.typingActive = false;
    state.typingActiveConversationId = null;
  }

  function trySendTypingEndBeforeClose() {
    const conversationId = state.typingActiveConversationId;
    if (!conversationId || !state.typingActive || !state.wsAuthed) {
      resetLocalTypingState();
      return;
    }
    try {
      wsSend(
        'typing',
        {
          msg_id_client: `typing_${Date.now()}_${Math.random().toString(16).slice(2)}`,
          conversation_id: conversationId,
          typing_state: 'end',
          supports_typing: true,
          client_sent_time_ms: Date.now(),
        },
        'typing'
      );
      appendLog({ self_typing_emit: 'end', conversation_id: conversationId, reason: 'ws-close' });
    } catch (err) {
      appendLog({ typing_send_failed: String(err && err.message ? err.message : err), reason: 'ws-close' });
    } finally {
      resetLocalTypingState();
    }
  }

  function closeWs({ suppressReconnect = false, code = 1000, reason = 'manual-close' } = {}) {
    if (!state.ws) {
      resetLocalTypingState();
      return;
    }
    trySendTypingEndBeforeClose();
    state.wsCloseSuppressReconnect = suppressReconnect;
    window.clearInterval(state.pingTimer);
    state.pingTimer = null;

    if (state.wsAuthPending) {
      window.clearTimeout(state.wsAuthPending.timeout);
      state.wsAuthPending.deferred.reject(new Error('WS_CLOSED'));
      state.wsAuthPending = null;
    }

    try {
      state.ws.close(code, reason);
    } catch {
      // ignore close errors
    }
    state.ws = null;
    state.wsAuthed = false;
    setWsBadge(WS_BADGE.DISCONNECTED);
    updateControls();
  }

  function wsSend(type, payload, prefix = 'ws') {
    if (!state.ws || state.ws.readyState !== WebSocket.OPEN) {
      throw new Error('WS_NOT_OPEN');
    }
    const frameId = randFrameId(prefix);
    state.ws.send(JSON.stringify({ type, ws_frame_id: frameId, payload }));
    return frameId;
  }

  function startPingLoop() {
    window.clearInterval(state.pingTimer);
    state.pingTimer = window.setInterval(() => {
      if (!state.wsAuthed) {
        return;
      }
      try {
        wsSend('ping', {}, 'ping');
      } catch (err) {
        appendLog({ ping_loop_error: String(err && err.message ? err.message : err) });
      }
    }, wsPingIntervalMs);
  }

  function handleWsAck(frame) {
    const payload = frame.payload && typeof frame.payload === 'object' ? frame.payload : {};

    if (state.wsAuthPending && frame.ws_frame_id === state.wsAuthPending.frameId && payload && payload.ok === true) {
      state.wsAuthed = true;
      state.wsAuthPending.deferred.resolve(true);
      state.wsAuthPending = null;
      setWsBadge(WS_BADGE.CONNECTED);
      updateControls();
      return;
    }

    if (state.pendingByFrameId.has(frame.ws_frame_id)) {
      const pending = state.pendingByFrameId.get(frame.ws_frame_id);
      state.pendingByFrameId.delete(frame.ws_frame_id);

      if (payload && typeof payload.msg_id_server === 'string' && payload.msg_id_server) {
        promotePendingMessage(
          pending.pending_id,
          pending.conversation_id,
          pending.msg_id_client,
          payload.msg_id_server,
          Number(payload.sent_time_ms || 0)
        );
      } else {
        markPendingStatus(pending.pending_id, pending.conversation_id, '');
      }
    }
  }

  function handleWsTypingEvent(typing) {
    if (!typing || typing.conversation_id !== state.selectedConversationId) {
      return;
    }
    const account = getActiveAccount();
    const contact = getSelectedContact();
    if (!account || !contact) {
      return;
    }

    const selfQiaoId = account.user_qiao_id;
    const peerQiaoId = contact.contact_qiao_id;
    if (!selfQiaoId || !peerQiaoId) {
      return;
    }
    const fromQiaoId = typeof typing.from_qiao_id === 'string' ? typing.from_qiao_id : '';
    const toQiaoId = typeof typing.to_qiao_id === 'string' ? typing.to_qiao_id : '';

    const fromPeer = fromQiaoId === peerQiaoId && toQiaoId === selfQiaoId;
    const fromSelf = fromQiaoId === selfQiaoId && toQiaoId === peerQiaoId;

    if (fromSelf) {
      appendLog({ self_typing_event: typing.typing_state || '-' });
      return;
    }
    if (!fromPeer) {
      return;
    }

    if (typing.typing_state === 'start') {
      clearTypingHint();
      el.typingHint.textContent = `${contactName(contact)} 正在输入...`;
      state.typingHintTimer = window.setTimeout(() => {
        clearTypingHint();
      }, PEER_TYPING_HINT_TIMEOUT_MS);
      return;
    }
    if (typing.typing_state === 'end') {
      clearTypingHint();
      return;
    }
    clearTypingHint();
  }

  function handleWsEvent(framePayload) {
    const eventType = framePayload && framePayload.event_type;
    if (eventType === 'message' && framePayload.message) {
      maybeHideTypingHintOnIncomingText(framePayload.message);
      ingestTimelineMessage(framePayload.message, 'ws-event');
      return;
    }
    if (eventType === 'typing' && framePayload.typing) {
      handleWsTypingEvent(framePayload.typing);
    }
  }

  function handleWsErrorFrame(framePayload) {
    const message =
      framePayload && typeof framePayload.message === 'string' && framePayload.message
        ? framePayload.message
        : 'WebSocket 错误';
    const code =
      framePayload && typeof framePayload.code === 'string' && framePayload.code ? framePayload.code : 'UNKNOWN_ERROR';
    setStatus(message);
    appendLog({ ws_error: framePayload });

    if (!state.wsAuthPending || !isAuthFailureFrame(framePayload)) {
      return;
    }
    const pending = state.wsAuthPending;
    window.clearTimeout(pending.timeout);
    pending.deferred.reject(new Error(`WS_AUTH_FAILED:${code}:${message}`));
    state.wsAuthPending = null;
    closeWs({ suppressReconnect: true, reason: 'auth-failure-frame' });
  }

  function onWsMessage(event) {
    const frame = parseWsFrame(event.data);
    if (!frame) {
      appendLog({ ws_invalid_frame: event.data });
      return;
    }

    if (frame.type === 'ack') {
      handleWsAck(frame);
      return;
    }
    if (frame.type === 'event') {
      handleWsEvent(frame.payload || {});
      return;
    }
    if (frame.type === 'error') {
      handleWsErrorFrame(frame.payload || {});
      return;
    }

    appendLog({ ws_unhandled_frame: frame });
  }

  function scheduleReconnect(reason, epoch) {
    if (state.reconnectTimer || state.reconnectInFlight) {
      return;
    }
    const account = getActiveAccount();
    if (!account || epoch !== currentEpoch()) {
      return;
    }

    const attemptIndex = Math.min(state.reconnectAttempt, reconnectDelaysMs.length - 1);
    const delay = reconnectDelaysMs[attemptIndex];
    state.reconnectAttempt += 1;

    setWsBadge(WS_BADGE.RECONNECTING);
    setStage(STAGE.RECONNECTING, `连接已断开，${Math.round(delay / 1000)} 秒后重连...`);

    state.reconnectTimer = window.setTimeout(() => {
      state.reconnectTimer = null;
      void reconnectNow(epoch, reason);
    }, delay);
  }

  async function openWsAndAuth(epoch) {
    const account = getActiveAccount();
    if (!account) {
      throw new Error('AUTH_REQUIRED');
    }

    if (state.ws && state.ws.readyState === WebSocket.OPEN && state.wsAuthed) {
      return;
    }

    closeWs({ suppressReconnect: true, reason: 'replace-connection' });
    await ensureValidAccessToken(account, { force: false });

    const wsPath = el.root.getAttribute('data-ws-path') || '/ws/messages';
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${location.host}${wsPath}`;

    const ws = new WebSocket(wsUrl);
    state.ws = ws;
    state.wsAuthed = false;
    setWsBadge(WS_BADGE.CONNECTING);

    const deferred = createDeferred();
    const timeout = window.setTimeout(() => {
      deferred.reject(new Error('WS_AUTH_TIMEOUT'));
    }, wsAuthTimeoutMs);
    state.wsAuthPending = {
      deferred,
      frameId: '',
      epoch,
      timeout,
    };

    ws.onopen = () => {
      try {
        const frameId = wsSend(
          'auth',
          {
            access_token: account.access_token,
            device_id: account.device_id,
          },
          'auth'
        );
        if (state.wsAuthPending) {
          state.wsAuthPending.frameId = frameId;
        }
      } catch (err) {
        deferred.reject(err);
      }
    };

    ws.onmessage = onWsMessage;

    ws.onerror = () => {
      appendLog({ ws_error_event: true });
    };

    ws.onclose = () => {
      resetLocalTypingState();
      window.clearInterval(state.pingTimer);
      state.pingTimer = null;
      state.ws = null;
      state.wsAuthed = false;

      const pending = state.wsAuthPending;
      if (pending) {
        pending.deferred.reject(new Error('WS_CLOSED'));
        window.clearTimeout(pending.timeout);
        state.wsAuthPending = null;
      }

      const suppressReconnect = state.wsCloseSuppressReconnect;
      state.wsCloseSuppressReconnect = false;

      if (!suppressReconnect && getActiveAccount() && epoch === currentEpoch()) {
        scheduleReconnect('socket-closed', epoch);
      } else {
        setWsBadge(WS_BADGE.DISCONNECTED);
      }
      updateControls();
    };

    try {
      await deferred.promise;
      if (state.wsAuthPending) {
        window.clearTimeout(state.wsAuthPending.timeout);
      }
      state.wsAuthPending = null;
      setWsBadge(WS_BADGE.CONNECTED);
      startPingLoop();
    } catch (err) {
      closeWs({ suppressReconnect: true, reason: 'auth-failed' });
      throw err;
    }
  }

  async function reconnectNow(epoch, reason) {
    if (state.reconnectInFlight) {
      return;
    }
    if (epoch !== currentEpoch()) {
      return;
    }
    if (!getActiveAccount()) {
      return;
    }

    state.reconnectInFlight = true;
    setStage(STAGE.RECONNECTING, '重连中...');
    setWsBadge(WS_BADGE.RECONNECTING);

    try {
      await openWsAndAuth(epoch);
      state.reconnectAttempt = 0;
      await pullOffline({ reason: `reconnect:${reason}`, silent: true });
      if (epoch === currentEpoch()) {
        setStage(STAGE.READY, '已重连。');
      }
    } catch (err) {
      const errorMessage = getErrorMessage(err);
      appendLog({ reconnect_failed: errorMessage });
      if (isAuthFailureError(err)) {
        closeWs({ suppressReconnect: true, reason: 'reconnect-auth-failed' });
        if (typeof setAuthBadge === 'function') {
          setAuthBadge(false);
        }
        if (epoch === currentEpoch()) {
          setStage(STAGE.UNAUTH, '会话已过期，请重新登录。');
        }
        return;
      }
      if (epoch === currentEpoch()) {
        scheduleReconnect('retry', epoch);
      }
    } finally {
      state.reconnectInFlight = false;
      updateControls();
    }
  }

  return Object.freeze({
    closeWs,
    wsSend,
    scheduleReconnect,
    openWsAndAuth,
    reconnectNow,
  });
}
