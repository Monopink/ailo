export function createViewRuntimeController({
  el,
  state,
  STAGE,
  formatGenderLabel,
  setAvatarImage,
  formatTimestamp,
  resetSnapshotPanelView,
  renderSnapshotPanelView,
  clearAutoLlmDetailsView,
  getActiveAccount,
}) {
  function accountLabel(account) {
    if (!account) return '-';
    const display = account.user && account.user.nickname ? account.user.nickname : account.identifier;
    return `${display} (${account.identifier})`;
  }

  function renderAccountSelect() {
    const prev = el.accountSelect.value;
    el.accountSelect.innerHTML = '';
    for (const account of state.vault.accounts) {
      const option = document.createElement('option');
      option.value = account.account_id;
      option.textContent = accountLabel(account);
      el.accountSelect.appendChild(option);
    }
    const activeId = state.vault.active_account_id || prev;
    if (activeId) {
      el.accountSelect.value = activeId;
    }
  }

  function resetSelfPanel() {
    el.selfName.textContent = '-';
    el.selfIdentifier.textContent = '-';
    el.selfUsername.textContent = '-';
    el.selfRegionGender.textContent = '-';
    el.selfBio.textContent = '-';
    el.selfDevice.textContent = '-';
    setAvatarImage(el.selfAvatarImg, '');
  }

  function renderSelfPanel(account) {
    if (!account) {
      resetSelfPanel();
      return;
    }
    const user = account.user || {};
    const username = typeof user.username === 'string' ? user.username.trim() : '';
    const qiaoId = account.user_qiao_id || user.qiao_id || '-';
    el.selfName.textContent = user.nickname || account.identifier || '-';
    el.selfIdentifier.textContent = qiaoId;
    el.selfUsername.textContent = username || '-';
    el.selfRegionGender.textContent = `${user.region || '-'} / ${formatGenderLabel(user.gender)}`;
    el.selfBio.textContent = user.bio || '-';
    el.selfDevice.textContent = account.device_id || '-';
    setAvatarImage(el.selfAvatarImg, user.avatar_url || '');
  }

  function resetPeerPanel() {
    el.peerName.textContent = '-';
    el.peerIdentifier.textContent = '-';
    el.peerUsername.textContent = '-';
    el.peerAliasRemark.textContent = '-';
    el.peerFlags.textContent = '-';
    el.peerRegionGender.textContent = '-';
    el.peerBio.textContent = '-';
    setAvatarImage(el.peerAvatarImg, '');
  }

  function renderPeerPanel(contact, detail = null, snapshot = null) {
    if (!contact) {
      resetPeerPanel();
      return;
    }
    const profile = detail && detail.profile ? detail.profile : contact.profile || {};
    const snapshotUsername =
      snapshot && typeof snapshot.instance_username === 'string' ? snapshot.instance_username.trim() : '';
    el.peerName.textContent = contact.alias || profile.nickname || contact.contact_qiao_id || '-';
    el.peerIdentifier.textContent = contact.contact_qiao_id || '-';
    el.peerUsername.textContent = snapshotUsername || '-';
    el.peerAliasRemark.textContent = `${contact.alias || '-'} / ${contact.remark || '-'}`;
    const flags = [];
    if (contact.is_pinned) flags.push('置顶');
    if (contact.is_muted) flags.push('免打扰');
    if (contact.is_blocked) flags.push('已拉黑');
    el.peerFlags.textContent = flags.length ? flags.join(', ') : '正常';
    el.peerRegionGender.textContent = `${profile.region || '-'} / ${formatGenderLabel(profile.gender)}`;
    el.peerBio.textContent = profile.bio || '-';
    setAvatarImage(el.peerAvatarImg, profile.avatar_url || '');
  }

  function resetSnapshotPanel() {
    resetSnapshotPanelView(el);
  }

  function renderSnapshotPanel(snapshot) {
    renderSnapshotPanelView(el, snapshot);
  }

  function updateControls() {
    const account = getActiveAccount();
    const hasAccount = Boolean(account);
    const authBusy = state.stage === STAGE.AUTHING || state.stage === STAGE.BOOTSTRAPPING;
    const conversationSelected = Boolean(state.selectedConversationId);
    const inputEnabled = hasAccount;
    const sendEnabled =
      hasAccount &&
      conversationSelected &&
      state.wsAuthed &&
      (state.stage === STAGE.READY || state.stage === STAGE.DEGRADED);

    el.btnLogin.disabled = authBusy;
    el.btnSwitchAccount.disabled = !state.vault.accounts.length || !el.accountSelect.value || authBusy;
    el.btnOpenLoginModal.disabled = authBusy;
    el.btnForgetAccount.disabled = !state.vault.accounts.length || !el.accountSelect.value || authBusy;
    el.btnReconnect.disabled = !hasAccount || authBusy;
    el.btnRefreshContacts.disabled = !hasAccount || authBusy;
    el.contactSearch.disabled = !hasAccount;

    el.messageInput.disabled = !inputEnabled;
    el.btnSend.disabled = !sendEnabled;

    el.btnPullOffline.disabled = !hasAccount || authBusy;
    el.btnPing.disabled = !state.wsAuthed;
    el.btnClearLocal.disabled = !hasAccount;
    el.btnRefreshSnapshot.disabled = !hasAccount || !conversationSelected;
    el.ackMsgId.disabled = !hasAccount;
    el.btnAck.disabled = !hasAccount;
    el.btnLlmRequestDetail.disabled = !hasAccount;
  }

  function getMessageSortTs(msg) {
    if (!msg) {
      return 0;
    }
    if (msg.direction === 'out') {
      return Number(msg.sent_at_ms || msg.client_sent_time_ms || 0);
    }
    return Number(msg.sent_at_ms || 0);
  }

  function getMessageDisplayTs(msg) {
    if (!msg) {
      return null;
    }
    if (msg.direction === 'out') {
      return msg.sent_at_ms || msg.client_sent_time_ms || null;
    }
    return msg.sent_at_ms || null;
  }

  function ensureConversationStore(conversationId) {
    if (!state.messagesByConversation.has(conversationId)) {
      state.messagesByConversation.set(conversationId, {
        order: [],
        byId: new Map(),
      });
    }
    return state.messagesByConversation.get(conversationId);
  }

  function sortConversationStore(store) {
    store.order.sort((a, b) => {
      const left = store.byId.get(a);
      const right = store.byId.get(b);
      const leftTs = getMessageSortTs(left);
      const rightTs = getMessageSortTs(right);
      if (leftTs !== rightTs) return leftTs - rightTs;
      return String(a).localeCompare(String(b));
    });
  }

  function shouldStickToBottom() {
    const node = el.messageList;
    const threshold = 80;
    return node.scrollTop + node.clientHeight >= node.scrollHeight - threshold;
  }

  function scrollToBottom() {
    el.messageList.scrollTop = el.messageList.scrollHeight;
  }

  function renderMessageRow(msg) {
    const row = document.createElement('div');
    row.className = `cc-msg-row ${msg.direction === 'out' ? 'cc-out' : 'cc-in'}`;

    const item = document.createElement('div');
    item.className = 'cc-msg-item';

    const bubble = document.createElement('div');
    bubble.className = 'cc-bubble';
    bubble.textContent = msg.content || '';

    const meta = document.createElement('div');
    meta.className = 'cc-msg-meta';

    const time = document.createElement('span');
    time.textContent = formatTimestamp(getMessageDisplayTs(msg));
    meta.appendChild(time);

    if (msg.status) {
      const status = document.createElement('span');
      status.className = 'cc-msg-status';
      status.textContent = msg.status;
      meta.appendChild(status);
    }

    const debug = document.createElement('div');
    debug.className = 'cc-msg-debug';

    const appendDebugLine = (label, value) => {
      const line = document.createElement('span');
      line.className = 'cc-msg-debug-line';
      const prefix = document.createTextNode(`${label}: `);
      const code = document.createElement('code');
      code.textContent = value;
      line.appendChild(prefix);
      line.appendChild(code);
      debug.appendChild(line);
    };

    appendDebugLine('msg_id_server', msg.msg_id_server || '-');
    if (msg.direction === 'out') {
      appendDebugLine('msg_id_client', msg.msg_id_client || '-');
    } else {
      const llmRequestLabel = msg.llm_request_id || '缺失（系统异常）';
      appendDebugLine('llm_request_id', llmRequestLabel);
    }
    if (msg.direction === 'out') {
      appendDebugLine(
        'timestamps',
        `sent_time_ms=${msg.sent_at_ms || '-'} client_sent_time_ms=${msg.client_sent_time_ms || '-'}`
      );
    } else {
      appendDebugLine('sent_time_ms', `${msg.sent_at_ms || '-'}`);
    }

    item.appendChild(bubble);
    item.appendChild(meta);
    item.appendChild(debug);
    row.appendChild(item);
    return row;
  }

  function renderConversation(conversationId, forceToBottom = false) {
    el.messageList.innerHTML = '';
    if (!conversationId) {
      return;
    }

    const store = ensureConversationStore(conversationId);
    sortConversationStore(store);
    for (const id of store.order) {
      const msg = store.byId.get(id);
      if (!msg) {
        continue;
      }
      el.messageList.appendChild(renderMessageRow(msg));
    }

    if (forceToBottom || shouldStickToBottom()) {
      scrollToBottom();
    }
  }

  function clearAutoLlmDetails() {
    clearAutoLlmDetailsView(el);
  }

  return Object.freeze({
    renderAccountSelect,
    resetSelfPanel,
    renderSelfPanel,
    resetPeerPanel,
    renderPeerPanel,
    resetSnapshotPanel,
    renderSnapshotPanel,
    updateControls,
    getMessageSortTs,
    ensureConversationStore,
    shouldStickToBottom,
    renderConversation,
    clearAutoLlmDetails,
  });
}
