export function createLlmDebugController({
  el,
  state,
  api,
  appendLog,
  ensureConversationStore,
  persistMessage,
  renderConversation,
  clearAutoLlmDetails,
  renderAutoLlmDetail,
  llmLinkDebounceMs,
  llmLinkBatchSize,
  llmAutoDetailsDebounceMs,
}) {
  function setCurrentLlmContext({ msgIdServer = '-', llmRequestId = '-' } = {}) {
    if (el.llmCurrentMsgIdServer) {
      el.llmCurrentMsgIdServer.textContent = msgIdServer || '-';
    }
    if (el.llmCurrentRequestId) {
      el.llmCurrentRequestId.textContent = llmRequestId || '-';
    }
  }

  function setLlmAutoStatus(text) {
    if (el.llmAutoStatus) {
      el.llmAutoStatus.textContent = String(text || '').trim();
    }
  }

  function normalizeLlmRequestId(value) {
    if (value === null || value === undefined) {
      return null;
    }
    const text = String(value).trim();
    if (!text || !/^\d+$/.test(text)) {
      return null;
    }
    return text;
  }

  async function requestLlmLinks(ids) {
    const unique = [...new Set(ids.filter(Boolean))];
    return api('/admin-api/debug/messages/llm-links', {
      method: 'POST',
      auth: false,
      body: { msg_id_servers: unique },
    });
  }

  async function requestLlmRequestDetails(llmRequestId) {
    return api('/admin-api/debug/messages/llm-request-detail', {
      method: 'POST',
      auth: false,
      body: { llm_request_id: llmRequestId },
    });
  }

  function latestIncomingMessageForSelectedConversation() {
    const conversationId = state.selectedConversationId;
    if (!conversationId) {
      return null;
    }
    const store = ensureConversationStore(conversationId);
    for (let i = store.order.length - 1; i >= 0; i -= 1) {
      const msg = store.byId.get(store.order[i]);
      if (msg && msg.direction === 'in') {
        return msg;
      }
    }
    return null;
  }

  function collectPendingLlmLookupMsgIds() {
    const conversationId = state.selectedConversationId;
    if (!conversationId) {
      return [];
    }
    const store = ensureConversationStore(conversationId);
    const ids = [];
    for (const id of store.order) {
      const msg = store.byId.get(id);
      if (!msg || !msg.msg_id_server) continue;
      if (msg.llm_request_id) continue;
      if (state.llmLinkByMsgId.has(msg.msg_id_server)) continue;
      ids.push(msg.msg_id_server);
    }
    return ids;
  }

  function applyLlmLinks(links) {
    if (!Array.isArray(links)) {
      return;
    }
    for (const item of links) {
      if (!item || typeof item.msg_id_server !== 'string') continue;
      const llmRequestId = normalizeLlmRequestId(item.llm_request_id);
      state.llmLinkByMsgId.set(item.msg_id_server, llmRequestId);
    }

    for (const [conversationId, store] of state.messagesByConversation.entries()) {
      let changed = false;
      for (const id of store.order) {
        const msg = store.byId.get(id);
        if (!msg || !msg.msg_id_server || msg.llm_request_id) continue;
        if (!state.llmLinkByMsgId.has(msg.msg_id_server)) continue;
        const llmRequestId = state.llmLinkByMsgId.get(msg.msg_id_server);
        if (!llmRequestId) continue;
        msg.llm_request_id = llmRequestId;
        changed = true;
        void persistMessage(msg);
      }
      if (changed && state.selectedConversationId === conversationId) {
        renderConversation(conversationId);
      }
    }
    scheduleAutoLlmDetailsRefresh();
  }

  async function fetchLlmLinksAuto() {
    if (state.llmLinksDisabled || state.llmLinkLookupInFlight) {
      return;
    }
    const ids = collectPendingLlmLookupMsgIds();
    if (!ids.length) {
      return;
    }

    state.llmLinkLookupInFlight = true;
    try {
      for (let i = 0; i < ids.length; i += llmLinkBatchSize) {
        const batch = ids.slice(i, i + llmLinkBatchSize);
        const res = await requestLlmLinks(batch);
        const links = res && Array.isArray(res.links) ? res.links : [];
        applyLlmLinks(links);
      }
    } catch (err) {
      const text = String(err && err.message ? err.message : err);
      if (text.includes('404') || text.includes('Not found')) {
        state.llmLinksDisabled = true;
        setLlmAutoStatus('llm-links 不可用');
      }
      appendLog({ llm_links_auto_failed: text });
    } finally {
      state.llmLinkLookupInFlight = false;
    }
  }

  function scheduleLlmLinkLookup() {
    if (state.llmLinksDisabled) {
      return;
    }
    if (state.llmLinkLookupTimer) {
      window.clearTimeout(state.llmLinkLookupTimer);
    }
    state.llmLinkLookupTimer = window.setTimeout(() => {
      state.llmLinkLookupTimer = null;
      void fetchLlmLinksAuto();
    }, llmLinkDebounceMs);
  }

  function scheduleAutoLlmDetailsRefresh() {
    if (!el.llmAutoFlags) {
      return;
    }
    if (state.llmAutoDetailsTimer) {
      window.clearTimeout(state.llmAutoDetailsTimer);
    }
    state.llmAutoDetailsTimer = window.setTimeout(() => {
      state.llmAutoDetailsTimer = null;
      void refreshAutoLlmDetails();
    }, llmAutoDetailsDebounceMs);
  }

  async function refreshAutoLlmDetails() {
    if (!el.llmAutoFlags || state.llmAutoDetailsInFlight) {
      return;
    }

    await fetchLlmLinksAuto();

    const latestIncoming = latestIncomingMessageForSelectedConversation();
    if (!latestIncoming) {
      clearAutoLlmDetails();
      setCurrentLlmContext();
      if (state.selectedConversationId && el.llmAutoFlags) {
        el.llmAutoFlags.textContent = '当前会话暂无入站消息。';
      }
      state.llmAutoDetailsRenderedId = 'none';
      return;
    }

    const llmRequestId = normalizeLlmRequestId(latestIncoming.llm_request_id);
    if (!llmRequestId) {
      clearAutoLlmDetails();
      setCurrentLlmContext({ msgIdServer: latestIncoming.msg_id_server || '-', llmRequestId: '-' });
      if (el.llmAutoFlags) {
        el.llmAutoFlags.textContent = '最新入站消息暂无 llm_request_id。';
      }
      state.llmAutoDetailsRenderedId = `missing:${latestIncoming.msg_id_server || '-'}`;
      return;
    }

    if (state.llmAutoDetailsRenderedId === llmRequestId) {
      return;
    }

    state.llmAutoDetailsInFlight = true;
    try {
      const detailsRes = await requestLlmRequestDetails(llmRequestId);
      const detail =
        detailsRes && detailsRes.detail && typeof detailsRes.detail === 'object' ? detailsRes.detail : null;
      renderAutoLlmDetail(detail);
      setCurrentLlmContext({
        msgIdServer: latestIncoming.msg_id_server || '-',
        llmRequestId,
      });
      state.llmAutoDetailsRenderedId = llmRequestId;
    } catch (err) {
      clearAutoLlmDetails();
      setCurrentLlmContext({
        msgIdServer: latestIncoming.msg_id_server || '-',
        llmRequestId,
      });
      if (el.llmAutoFlags) {
        el.llmAutoFlags.textContent = `自动详情拉取失败：${String(err && err.message ? err.message : err)}`;
      }
    } finally {
      state.llmAutoDetailsInFlight = false;
    }
  }

  async function fetchManualLlmRequestDetail() {
    const raw = (el.llmRequestIdInput.value || '').trim();
    const llmRequestId = normalizeLlmRequestId(raw);
    if (!llmRequestId) {
      setLlmAutoStatus('手动查询参数无效');
      if (el.llmAutoFlags) {
        el.llmAutoFlags.textContent = '请输入有效的 llm_request_id。';
      }
      appendLog({ llm_request_manual_lookup_invalid_input: raw || null });
      return;
    }

    try {
      const detailsRes = await requestLlmRequestDetails(llmRequestId);
      const detail =
        detailsRes && detailsRes.detail && typeof detailsRes.detail === 'object' ? detailsRes.detail : null;
      renderAutoLlmDetail(detail);
      setCurrentLlmContext({ msgIdServer: '-', llmRequestId });
      state.llmAutoDetailsRenderedId = llmRequestId;
      setLlmAutoStatus('手动查询');
      appendLog({
        llm_request_manual_lookup: { llm_request_id: llmRequestId, found: Boolean(detail && detail.found) },
      });
      if (!detail || !detail.found) {
        if (el.llmAutoFlags) {
          el.llmAutoFlags.textContent = `未找到 llm_request_id=${llmRequestId} 的详情。`;
        }
      }
    } catch (err) {
      const text = String(err && err.message ? err.message : err);
      if (el.llmAutoFlags) {
        el.llmAutoFlags.textContent = `手动查询失败：${text}`;
      }
      setLlmAutoStatus('手动查询失败');
      appendLog({ llm_request_manual_lookup_failed: { llm_request_id: llmRequestId, error: text } });
    }
  }

  return Object.freeze({
    fetchManualLlmRequestDetail,
    scheduleAutoLlmDetailsRefresh,
    scheduleLlmLinkLookup,
    setCurrentLlmContext,
  });
}
