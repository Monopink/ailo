export function createContactsRuntimeController({
  el,
  state,
  api,
  appendLog,
  setStatus,
  updateControls,
  getActiveAccount,
  renderConversation,
  resetPeerPanel,
  renderPeerPanel,
  resetSnapshotPanel,
  renderSnapshotPanel,
  clearAutoLlmDetails,
  flushAck,
  stopTypingIfNeeded,
  hydrateConversationFromLocal,
  scheduleLlmLinkLookup,
  scheduleAutoLlmDetailsRefresh,
  snapshotAutoRefreshDebounceMs,
}) {
  function contactName(contact) {
    return (
      contact.alias ||
      (contact.profile && contact.profile.nickname) ||
      contact.contact_qiao_id ||
      contact.conversation_id
    );
  }

  function renderContacts() {
    const query = (state.contactFilter || '').trim().toLowerCase();
    const filtered = state.contacts.filter((item) => {
      if (!query) {
        return true;
      }
      const text = [
        contactName(item),
        item.contact_qiao_id || '',
        item.conversation_id || '',
        (item.profile && item.profile.nickname) || '',
      ]
        .join(' ')
        .toLowerCase();
      return text.includes(query);
    });

    el.contactsCount.textContent = String(filtered.length);
    el.contactList.innerHTML = '';

    for (const contact of filtered) {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'cc-contact-item';
      btn.dataset.conversationId = contact.conversation_id;
      if (contact.conversation_id === state.selectedConversationId) {
        btn.classList.add('active');
      }

      const title = document.createElement('div');
      title.className = 'fw-semibold text-truncate';
      title.textContent = contactName(contact);

      const subtitle = document.createElement('div');
      subtitle.className = 'small text-muted text-truncate';
      const flagParts = [];
      if (contact.is_pinned) flagParts.push('置顶');
      if (contact.is_muted) flagParts.push('免打扰');
      if (contact.is_blocked) flagParts.push('已拉黑');
      subtitle.textContent = `${contact.contact_qiao_id || '-'}${flagParts.length ? ` - ${flagParts.join(',')}` : ''}`;

      btn.appendChild(title);
      btn.appendChild(subtitle);
      btn.addEventListener('click', () => {
        selectConversation(contact.conversation_id, { forceBottom: true });
      });

      el.contactList.appendChild(btn);
    }
  }

  function getSelectedContact() {
    if (!state.selectedConversationId) {
      return null;
    }
    return state.contacts.find((item) => item.conversation_id === state.selectedConversationId) || null;
  }

  async function loadContactDetail(conversationId) {
    if (!conversationId) return null;
    if (state.detailsByConversation.has(conversationId)) {
      return state.detailsByConversation.get(conversationId);
    }
    const detail = await api(`/api/v1/contacts/${encodeURIComponent(conversationId)}`, {
      method: 'GET',
      auth: true,
    });
    state.detailsByConversation.set(conversationId, detail);
    return detail;
  }

  async function refreshInstanceSnapshot({ silent = false } = {}) {
    const contact = getSelectedContact();
    if (!contact || !contact.conversation_id) {
      resetSnapshotPanel();
      return;
    }
    const account = getActiveAccount();
    if (!account) {
      return;
    }

    if (!silent) {
      el.snapshotStatus.textContent = '';
    }
    try {
      const res = await api('/admin-api/debug/instances/snapshot', {
        method: 'POST',
        auth: false,
        body: {
          conversation_id: contact.conversation_id,
          instance_qiao_id: contact.contact_qiao_id || null,
          user_qiao_id: account.user_qiao_id || null,
        },
      });
      renderSnapshotPanel(res);
      if (state.selectedConversationId === contact.conversation_id) {
        const detail = state.detailsByConversation.get(contact.conversation_id) || null;
        renderPeerPanel(contact, detail, res);
      }
    } catch (err) {
      const text = String(err && err.message ? err.message : err);
      el.snapshotStatus.textContent = `失败：${text}`;
      if (!silent) {
        appendLog({ snapshot_failed: text });
      }
    }
  }

  function scheduleSnapshotRefresh() {
    if (!state.selectedConversationId) {
      return;
    }
    if (state.snapshotAutoRefreshTimer) {
      window.clearTimeout(state.snapshotAutoRefreshTimer);
    }
    state.snapshotAutoRefreshTimer = window.setTimeout(() => {
      state.snapshotAutoRefreshTimer = null;
      void refreshInstanceSnapshot({ silent: true });
    }, snapshotAutoRefreshDebounceMs);
  }

  function selectConversation(conversationId, { forceBottom = false } = {}) {
    if (!conversationId) {
      return;
    }
    if (state.selectedConversationId && state.selectedConversationId !== conversationId) {
      stopTypingIfNeeded();
    }
    state.selectedConversationId = conversationId;
    state.llmAutoDetailsRenderedId = null;
    clearAutoLlmDetails();

    for (const node of el.contactList.querySelectorAll('.cc-contact-item')) {
      node.classList.toggle('active', node.dataset.conversationId === conversationId);
    }

    const contact = getSelectedContact();
    if (contact) {
      el.chatTitle.textContent = contactName(contact);
      el.chatSubtitle.textContent = contact.conversation_id || '-';
      renderPeerPanel(contact, state.detailsByConversation.get(conversationId) || null);
    } else {
      el.chatTitle.textContent = '请选择聊天';
      el.chatSubtitle.textContent = '-';
      resetPeerPanel();
      resetSnapshotPanel();
    }

    renderConversation(conversationId, forceBottom);
    scheduleLlmLinkLookup();
    void flushAck('conversation-switch');
    void (async () => {
      try {
        const detail = await loadContactDetail(conversationId);
        if (state.selectedConversationId === conversationId) {
          renderPeerPanel(contact || detail, detail);
        }
      } catch (err) {
        appendLog({ contact_detail_failed: String(err && err.message ? err.message : err) });
      }
      await hydrateConversationFromLocal(conversationId, { forceBottom: false });
      await refreshInstanceSnapshot({ silent: true });
      scheduleLlmLinkLookup();
      scheduleAutoLlmDetailsRefresh();
    })();
    updateControls();
  }

  function resetChatSurface() {
    stopTypingIfNeeded();
    state.contacts = [];
    state.contactFilter = '';
    state.selectedConversationId = null;
    state.detailsByConversation.clear();
    state.messagesByConversation.clear();
    state.llmLinkByMsgId.clear();
    state.pendingByFrameId.clear();
    state.pendingByClientId.clear();
    state.llmLinkLookupInFlight = false;
    state.llmLinksDisabled = false;
    state.llmAutoDetailsRenderedId = null;
    if (state.llmLinkLookupTimer) {
      window.clearTimeout(state.llmLinkLookupTimer);
      state.llmLinkLookupTimer = null;
    }
    if (state.llmAutoDetailsTimer) {
      window.clearTimeout(state.llmAutoDetailsTimer);
      state.llmAutoDetailsTimer = null;
    }
    if (state.snapshotAutoRefreshTimer) {
      window.clearTimeout(state.snapshotAutoRefreshTimer);
      state.snapshotAutoRefreshTimer = null;
    }
    state.storage.loadedKeys.clear();
    state.ack.candidate = null;
    state.ack.lastAcked = null;
    state.ack.stagedCount = 0;

    el.contactSearch.value = '';
    el.contactsCount.textContent = '0';
    el.contactList.innerHTML = '';
    el.chatTitle.textContent = '请选择聊天';
    el.chatSubtitle.textContent = '-';
    el.messageList.innerHTML = '';
    el.typingHint.textContent = '';
    resetPeerPanel();
    resetSnapshotPanel();
    if (el.llmAutoStatus) {
      el.llmAutoStatus.textContent = '等待中';
    }
    if (el.llmCurrentMsgIdServer) {
      el.llmCurrentMsgIdServer.textContent = '-';
    }
    if (el.llmCurrentRequestId) {
      el.llmCurrentRequestId.textContent = '-';
    }
    clearAutoLlmDetails();
  }

  async function loadContacts({ silent = false } = {}) {
    const res = await api('/api/v1/contacts?limit=100', { method: 'GET', auth: true });
    const items = res && Array.isArray(res.items) ? res.items : [];
    state.contacts = items;
    state.detailsByConversation.clear();
    renderContacts();

    if (!items.length) {
      state.selectedConversationId = null;
      el.chatTitle.textContent = '暂无联系人';
      el.chatSubtitle.textContent = '-';
      el.messageList.innerHTML = '';
      resetPeerPanel();
      resetSnapshotPanel();
      return items;
    }

    const selectedStillExists = items.some((it) => it.conversation_id === state.selectedConversationId);
    if (!selectedStillExists) {
      selectConversation(items[0].conversation_id, { forceBottom: true });
    } else if (state.selectedConversationId) {
      selectConversation(state.selectedConversationId, { forceBottom: false });
    }

    if (!silent) {
      setStatus(`联系人已加载：${items.length}`);
    }
    return items;
  }

  return Object.freeze({
    contactName,
    renderContacts,
    getSelectedContact,
    refreshInstanceSnapshot,
    scheduleSnapshotRefresh,
    selectConversation,
    resetChatSurface,
    loadContacts,
  });
}
