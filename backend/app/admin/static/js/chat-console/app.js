import {
  createDeferred,
  randFrameId,
  bytesToBase64,
  base64ToBytes,
  safeJsonParse,
  nowMs,
  makeDeviceId,
  makeAccountId,
  createApiClient,
  extractErrorMessage,
  parseWsFrame,
  normalizeCursor,
  compareCursor,
} from './core.js';
import {
  getPartitionKey,
  withDbStore as withDbStoreUtil,
  openLocalDb as openLocalDbUtil,
  toPersistedMessage,
} from './storage.js';
import { normalizeVaultAccounts, resolveActiveAccountId, createVaultCrypto } from './session.js';
import {
  formatGenderLabel,
  setAvatarImage,
  formatTimestamp,
  resetSnapshotPanel as resetSnapshotPanelView,
  renderSnapshotPanel as renderSnapshotPanelView,
  clearAutoLlmDetails as clearAutoLlmDetailsView,
  renderAutoLlmDetail as renderAutoLlmDetailView,
} from './ui.js';
import { bindChatConsoleEvents } from './events.js';
import { createLlmDebugController } from './llm-debug.js';
import { createWsRuntimeController } from './ws-runtime.js';
import { createAccountRuntimeController } from './account-runtime.js';
import { createContactsRuntimeController } from './contacts-runtime.js';
import { createMessageRuntimeController } from './message-runtime.js';
import { createViewRuntimeController } from './view-runtime.js';

(() => {
  'use strict';

  const STAGE = Object.freeze({
    UNAUTH: 'UNAUTH',
    AUTHING: 'AUTHING',
    BOOTSTRAPPING: 'BOOTSTRAPPING',
    READY: 'READY',
    RECONNECTING: 'RECONNECTING',
    DEGRADED: 'DEGRADED',
  });

  const WS_BADGE = Object.freeze({
    DISCONNECTED: 'DISCONNECTED',
    CONNECTING: 'CONNECTING',
    CONNECTED: 'CONNECTED',
    RECONNECTING: 'RECONNECTING',
  });

  const VAULT_STORAGE_KEY = 'cc_account_vault_v1';
  const VAULT_MASTER_KEY = 'cc_account_vault_master_v1';
  const VAULT_SALT_KEY = 'cc_account_vault_salt_v1';
  const MAX_VAULT_ACCOUNTS = 20;
  const TOKEN_REFRESH_SKEW_MS = 60000;
  const WS_AUTH_TIMEOUT_MS = 10000;
  const WS_PING_INTERVAL_MS = 25000;
  const ACK_FLUSH_DELAY_MS = 1200;
  const ACK_BATCH_THRESHOLD = 5;
  const OFFLINE_PAGE_LIMIT = 100;
  const OFFLINE_MAX_PAGES = 50;
  const RECONNECT_DELAYS_MS = [1000, 2000, 4000, 8000, 12000, 20000, 30000];
  const LOG_LINE_LIMIT = 350;
  const LLM_LINK_DEBOUNCE_MS = 220;
  const LLM_LINK_BATCH_SIZE = 80;
  const LLM_AUTO_DETAILS_DEBOUNCE_MS = 240;
  const SNAPSHOT_AUTO_REFRESH_DEBOUNCE_MS = 500;
  const IDB_DB_NAME = 'chat_console_messages_v1';
  const IDB_STORE_MESSAGES = 'messages';
  const IDB_VERSION = 1;
  const LOCAL_MESSAGE_LIMIT_PER_CONVERSATION = 400;
  const LOCAL_MESSAGE_TTL_MS = 1000 * 60 * 60 * 24 * 7;

  const el = {
    root: document.querySelector('.cc-root'),
    authBadge: document.getElementById('cc_auth_badge'),
    wsBadge: document.getElementById('cc_ws_badge'),
    stage: document.getElementById('cc_stage'),
    status: document.getElementById('cc_status'),

    selfName: document.getElementById('cc_self_name'),
    selfIdentifier: document.getElementById('cc_self_identifier'),
    selfUsername: document.getElementById('cc_self_username'),
    selfAvatarImg: document.getElementById('cc_self_avatar_img'),
    selfRegionGender: document.getElementById('cc_self_region_gender'),
    selfBio: document.getElementById('cc_self_bio'),
    selfDevice: document.getElementById('cc_self_device'),

    accountSelect: document.getElementById('cc_account_select'),
    btnSwitchAccount: document.getElementById('cc_btn_switch_account'),
    btnOpenLoginModal: document.getElementById('cc_btn_open_login_modal'),
    btnForgetAccount: document.getElementById('cc_btn_forget_account'),
    btnReconnect: document.getElementById('cc_btn_reconnect'),

    identifier: document.getElementById('cc_identifier'),
    password: document.getElementById('cc_password'),
    btnLogin: document.getElementById('cc_btn_login'),

    contactSearch: document.getElementById('cc_contact_search'),
    contactsCount: document.getElementById('cc_contacts_count'),
    contactList: document.getElementById('cc_contact_list'),
    btnRefreshContacts: document.getElementById('cc_btn_refresh_contacts'),

    chatTitle: document.getElementById('cc_chat_title'),
    chatSubtitle: document.getElementById('cc_chat_subtitle'),
    messageList: document.getElementById('cc_message_list'),
    messageInput: document.getElementById('cc_message_input'),
    btnSend: document.getElementById('cc_btn_send'),
    typingHint: document.getElementById('cc_typing_hint'),

    peerName: document.getElementById('cc_peer_name'),
    peerIdentifier: document.getElementById('cc_peer_identifier'),
    peerUsername: document.getElementById('cc_peer_username'),
    peerAvatarImg: document.getElementById('cc_peer_avatar_img'),
    peerAliasRemark: document.getElementById('cc_peer_alias_remark'),
    peerFlags: document.getElementById('cc_peer_flags'),
    peerRegionGender: document.getElementById('cc_peer_region_gender'),
    peerBio: document.getElementById('cc_peer_bio'),

    snapshotStatus: document.getElementById('cc_snapshot_status'),
    snapshotBase: document.getElementById('cc_snapshot_base'),
    snapshotStylePersonality: document.getElementById('cc_snapshot_style_personality'),
    snapshotRelationship: document.getElementById('cc_snapshot_relationship'),
    snapshotMemoryItems: document.getElementById('cc_snapshot_memory_items'),
    btnRefreshSnapshot: document.getElementById('cc_btn_refresh_snapshot'),

    btnPullOffline: document.getElementById('cc_btn_pull_offline'),
    btnPing: document.getElementById('cc_btn_ping'),
    btnClearLocal: document.getElementById('cc_btn_clear_local'),
    ackMsgId: document.getElementById('cc_ack_msg_id'),
    btnAck: document.getElementById('cc_btn_ack'),
    llmRequestIdInput: document.getElementById('cc_llm_request_id_input'),
    btnLlmRequestDetail: document.getElementById('cc_btn_llm_request_detail'),
    llmCurrentMsgIdServer: document.getElementById('cc_llm_current_msg_id_server'),
    llmCurrentRequestId: document.getElementById('cc_llm_current_request_id'),
    llmAutoStatus: document.getElementById('cc_llm_auto_status'),
    llmAutoSystemPrompt: document.getElementById('cc_llm_auto_system_prompt'),
    llmAutoFlags: document.getElementById('cc_llm_auto_flags'),
    llmAutoInternalThoughts: document.getElementById('cc_llm_auto_internal_thoughts'),
    llmAutoCurrentState: document.getElementById('cc_llm_auto_current_state'),
    llmAutoOutgoing: document.getElementById('cc_llm_auto_outgoing'),
    llmAutoFollowup: document.getElementById('cc_llm_auto_followup'),
    llmAutoScores: document.getElementById('cc_llm_auto_scores'),
    llmAutoRelationship: document.getElementById('cc_llm_auto_relationship'),
    llmAutoMemoryOps: document.getElementById('cc_llm_auto_memory_ops'),
    llmAutoPerf: document.getElementById('cc_llm_auto_perf'),
    llmAutoRequest: document.getElementById('cc_llm_auto_request'),
    llmAutoResponse: document.getElementById('cc_llm_auto_response'),

    log: document.getElementById('cc_log'),
    btnClearLog: document.getElementById('cc_btn_clear_log'),

    loginModal: document.getElementById('cc_login_modal'),
  };

  if (!el.root || !el.status || !el.log) {
    return;
  }

  const state = {
    stage: STAGE.UNAUTH,
    wsBadge: WS_BADGE.DISCONNECTED,

    vault: {
      accounts: [],
      active_account_id: null,
    },

    ws: null,
    wsAuthed: false,
    wsAuthPending: null,
    wsCloseSuppressReconnect: false,
    pingTimer: null,

    reconnectTimer: null,
    reconnectInFlight: false,
    reconnectAttempt: 0,

    contacts: [],
    contactFilter: '',
    selectedConversationId: null,

    messagesByConversation: new Map(),
    pendingByFrameId: new Map(),
    pendingByClientId: new Map(),

    typingActive: false,
    typingActiveConversationId: null,
    typingStartBufferTimer: null,
    isMessageInputComposing: false,
    typingHintTimer: null,

    selfTypingLogTimer: null,
    loginModalInstance: null,

    ack: {
      candidate: null,
      lastAcked: null,
      stagedCount: 0,
      flushTimer: null,
      inFlight: false,
    },

    offlineInFlight: false,
    sessionEpoch: 0,

    detailsByConversation: new Map(),
    llmLinkByMsgId: new Map(),
    llmLinkLookupTimer: null,
    llmLinkLookupInFlight: false,
    llmLinksDisabled: false,
    llmAutoDetailsTimer: null,
    llmAutoDetailsInFlight: false,
    llmAutoDetailsRenderedId: null,
    snapshotAutoRefreshTimer: null,

    storage: {
      available: false,
      db: null,
      writeQueue: Promise.resolve(),
      autoAckEnabled: true,
      loadedKeys: new Set(),
    },
  };

  const api = createApiClient({
    getActiveAccount,
    ensureValidAccessToken,
    refreshAccessToken,
  });
  const withDbStore = (mode, executor) => withDbStoreUtil(state.storage.db, IDB_STORE_MESSAGES, mode, executor);
  const openLocalDb = () =>
    openLocalDbUtil({
      dbName: IDB_DB_NAME,
      dbVersion: IDB_VERSION,
      storeName: IDB_STORE_MESSAGES,
    });
  const { encryptVaultPayload, decryptVaultPayload } = createVaultCrypto({
    masterKey: VAULT_MASTER_KEY,
    saltKey: VAULT_SALT_KEY,
    bytesToBase64,
    base64ToBytes,
    safeJsonParse,
  });
  let messageRuntime = null;
  const llmDebug = createLlmDebugController({
    el,
    state,
    api,
    appendLog,
    ensureConversationStore,
    persistMessage: (msg) => (messageRuntime ? messageRuntime.persistMessage(msg) : Promise.resolve(false)),
    renderConversation,
    clearAutoLlmDetails,
    renderAutoLlmDetail: (item) => renderAutoLlmDetailView(el, item),
    llmLinkDebounceMs: LLM_LINK_DEBOUNCE_MS,
    llmLinkBatchSize: LLM_LINK_BATCH_SIZE,
    llmAutoDetailsDebounceMs: LLM_AUTO_DETAILS_DEBOUNCE_MS,
  });
  const wsRuntime = createWsRuntimeController({
    el,
    state,
    WS_BADGE,
    STAGE,
    reconnectDelaysMs: RECONNECT_DELAYS_MS,
    wsAuthTimeoutMs: WS_AUTH_TIMEOUT_MS,
    wsPingIntervalMs: WS_PING_INTERVAL_MS,
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
  });
  const accountRuntime = createAccountRuntimeController({
    el,
    state,
    api,
    STAGE,
    maxVaultAccounts: MAX_VAULT_ACCOUNTS,
    tokenRefreshSkewMs: TOKEN_REFRESH_SKEW_MS,
    vaultStorageKey: VAULT_STORAGE_KEY,
    encryptVaultPayload,
    decryptVaultPayload,
    normalizeVaultAccounts,
    resolveActiveAccountId,
    nowMs,
    makeDeviceId,
    makeAccountId,
    extractErrorMessage,
    appendLog,
    setStatus,
    setStage,
    setAuthBadge,
    updateControls,
    renderAccountSelect,
    renderSelfPanel,
    resetChatSurface,
    resetSelfPanel,
    closeLoginModal,
    hasSignedInAccount,
    bumpEpoch,
    currentEpoch,
    getActiveAccount,
    closeWs,
    openWsAndAuth,
    scheduleReconnect,
    loadContacts,
    hydrateConversationFromLocal,
    pullOffline,
  });
  const contactsRuntime = createContactsRuntimeController({
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
    stopTypingIfNeeded: () => {
      if (messageRuntime) {
        messageRuntime.stopTypingIfNeeded();
      }
    },
    hydrateConversationFromLocal,
    scheduleLlmLinkLookup,
    scheduleAutoLlmDetailsRefresh,
    snapshotAutoRefreshDebounceMs: SNAPSHOT_AUTO_REFRESH_DEBOUNCE_MS,
  });
  messageRuntime = createMessageRuntimeController({
    el,
    state,
    api,
    STAGE,
    ackFlushDelayMs: ACK_FLUSH_DELAY_MS,
    ackBatchThreshold: ACK_BATCH_THRESHOLD,
    offlinePageLimit: OFFLINE_PAGE_LIMIT,
    offlineMaxPages: OFFLINE_MAX_PAGES,
    localMessageLimitPerConversation: LOCAL_MESSAGE_LIMIT_PER_CONVERSATION,
    localMessageTtlMs: LOCAL_MESSAGE_TTL_MS,
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
  });
  const viewRuntime = createViewRuntimeController({
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
  });

  function formatLogTimestamp(ms) {
    const date = new Date(ms);
    const y = date.getFullYear();
    const m = String(date.getMonth() + 1).padStart(2, '0');
    const d = String(date.getDate()).padStart(2, '0');
    const hh = String(date.getHours()).padStart(2, '0');
    const mm = String(date.getMinutes()).padStart(2, '0');
    const ss = String(date.getSeconds()).padStart(2, '0');
    const sss = String(date.getMilliseconds()).padStart(3, '0');
    return `${y}-${m}-${d} ${hh}:${mm}:${ss}.${sss}`;
  }

  function appendLog(value) {
    const line = typeof value === 'string' ? value : JSON.stringify(value, null, 2);
    const next = `[${formatLogTimestamp(Date.now())}] ${line}\n`;
    el.log.textContent += next;
    const lines = el.log.textContent.split('\n');
    if (lines.length > LOG_LINE_LIMIT) {
      el.log.textContent = `${lines.slice(lines.length - LOG_LINE_LIMIT).join('\n')}\n`;
    }
    el.log.scrollTop = el.log.scrollHeight;
  }

  function clearLog() {
    el.log.textContent = '';
  }

  function normalizeStageLike(value) {
    return String(value || '')
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '');
  }

  function shouldSuppressStatusText(text) {
    const statusNorm = normalizeStageLike(text);
    if (!statusNorm) {
      return true;
    }
    const stageNorm = normalizeStageLike(state.stage);
    if (!stageNorm) {
      return false;
    }
    return statusNorm === stageNorm;
  }

  function setStatus(text) {
    el.status.textContent = shouldSuppressStatusText(text) ? '' : text;
  }

  function setAuthBadge(isSignedIn) {
    el.authBadge.className = isSignedIn ? 'badge bg-success-lt' : 'badge bg-secondary-lt';
    el.authBadge.textContent = isSignedIn ? '已登录' : '未登录';
  }

  function setWsBadge(mode) {
    state.wsBadge = mode;
    if (mode === WS_BADGE.CONNECTED) {
      el.wsBadge.className = 'badge bg-success-lt';
      el.wsBadge.textContent = '已连接';
      return;
    }
    if (mode === WS_BADGE.CONNECTING) {
      el.wsBadge.className = 'badge bg-warning-lt';
      el.wsBadge.textContent = '连接中';
      return;
    }
    if (mode === WS_BADGE.RECONNECTING) {
      el.wsBadge.className = 'badge bg-warning-lt';
      el.wsBadge.textContent = '重连中';
      return;
    }
    el.wsBadge.className = 'badge bg-secondary-lt';
    el.wsBadge.textContent = '未连接';
  }

  function setStage(stage, text) {
    state.stage = stage;
    el.stage.textContent = stage;
    if (text) {
      setStatus(text);
    }
    updateControls();
  }

  function getLoginModalInstance() {
    if (!el.loginModal || !window.bootstrap || !window.bootstrap.Modal) {
      return null;
    }
    if (!state.loginModalInstance) {
      state.loginModalInstance = new window.bootstrap.Modal(el.loginModal);
    }
    return state.loginModalInstance;
  }

  function openLoginModal() {
    if (!el.loginModal) return;
    const modal = getLoginModalInstance();
    if (modal) {
      modal.show();
    } else {
      el.loginModal.classList.add('show');
      el.loginModal.style.display = 'block';
      el.loginModal.removeAttribute('aria-hidden');
    }
    window.setTimeout(() => {
      if (el.identifier) {
        el.identifier.focus();
      }
    }, 0);
  }

  function closeLoginModal() {
    if (!el.loginModal) return;
    const modal = getLoginModalInstance();
    if (modal) {
      modal.hide();
      return;
    }
    el.loginModal.classList.remove('show');
    el.loginModal.style.display = 'none';
    el.loginModal.setAttribute('aria-hidden', 'true');
  }

  function currentEpoch() {
    return state.sessionEpoch;
  }

  function bumpEpoch() {
    state.sessionEpoch += 1;
    return state.sessionEpoch;
  }

  function getActiveAccount() {
    const activeId = state.vault.active_account_id;
    if (!activeId) {
      return null;
    }
    return state.vault.accounts.find((item) => item.account_id === activeId) || null;
  }

  function hasSignedInAccount() {
    const account = getActiveAccount();
    return Boolean(account && account.refresh_token);
  }

  function renderAccountSelect() {
    viewRuntime.renderAccountSelect();
  }

  function resetSelfPanel() {
    viewRuntime.resetSelfPanel();
  }

  function renderSelfPanel(account) {
    viewRuntime.renderSelfPanel(account);
  }

  function resetPeerPanel() {
    viewRuntime.resetPeerPanel();
  }

  function renderPeerPanel(contact, detail = null) {
    viewRuntime.renderPeerPanel(contact, detail);
  }

  function resetSnapshotPanel() {
    viewRuntime.resetSnapshotPanel();
  }

  function renderSnapshotPanel(snapshot) {
    viewRuntime.renderSnapshotPanel(snapshot);
  }

  function updateControls() {
    viewRuntime.updateControls();
  }

  function getMessageSortTs(msg) {
    return viewRuntime.getMessageSortTs(msg);
  }

  function ensureConversationStore(conversationId) {
    return viewRuntime.ensureConversationStore(conversationId);
  }

  function shouldStickToBottom() {
    return viewRuntime.shouldStickToBottom();
  }

  function renderConversation(conversationId, forceToBottom = false) {
    viewRuntime.renderConversation(conversationId, forceToBottom);
  }

  function getStorageAccountId() {
    const account = getActiveAccount();
    return account ? account.account_id : null;
  }

  async function setStorageUnavailable(reason) {
    return messageRuntime.setStorageUnavailable(reason);
  }

  async function initializeLocalStorage() {
    return messageRuntime.initializeLocalStorage();
  }

  function enqueueStorageTask(task) {
    return messageRuntime.enqueueStorageTask(task);
  }

  async function waitForStorageIdle() {
    return messageRuntime.waitForStorageIdle();
  }

  async function cleanupExpiredLocalRecords() {
    return messageRuntime.cleanupExpiredLocalRecords();
  }

  async function persistMessage(msg) {
    return messageRuntime.persistMessage(msg);
  }

  async function pruneLocalPartition(partitionKey) {
    return messageRuntime.pruneLocalPartition(partitionKey);
  }

  async function hydrateConversationFromLocal(conversationId, { forceBottom = false } = {}) {
    return messageRuntime.hydrateConversationFromLocal(conversationId, { forceBottom });
  }

  async function clearLocalMessagesForActiveAccount() {
    return messageRuntime.clearLocalMessagesForActiveAccount();
  }

  function contactName(contact) {
    return contactsRuntime.contactName(contact);
  }

  function renderContacts() {
    contactsRuntime.renderContacts();
  }

  function getSelectedContact() {
    return contactsRuntime.getSelectedContact();
  }

  async function refreshInstanceSnapshot({ silent = false } = {}) {
    return contactsRuntime.refreshInstanceSnapshot({ silent });
  }

  function scheduleSnapshotRefresh() {
    contactsRuntime.scheduleSnapshotRefresh();
  }

  function clearAutoLlmDetails() {
    viewRuntime.clearAutoLlmDetails();
  }

  function selectConversation(conversationId, { forceBottom = false } = {}) {
    contactsRuntime.selectConversation(conversationId, { forceBottom });
  }

  function resetChatSurface() {
    contactsRuntime.resetChatSurface();
  }

  async function loadVault() {
    return accountRuntime.loadVault();
  }

  async function saveVault() {
    return accountRuntime.saveVault();
  }

  async function refreshAccessToken(account) {
    return accountRuntime.refreshAccessToken(account);
  }

  async function ensureValidAccessToken(account, options = {}) {
    return accountRuntime.ensureValidAccessToken(account, options);
  }

  async function fetchSelfProfile(account) {
    return accountRuntime.fetchSelfProfile(account);
  }

  function closeWs(opts = {}) {
    wsRuntime.closeWs(opts);
  }

  function wsSend(type, payload, prefix = 'ws') {
    return wsRuntime.wsSend(type, payload, prefix);
  }

  function scheduleReconnect(reason, epoch) {
    wsRuntime.scheduleReconnect(reason, epoch);
  }

  async function openWsAndAuth(epoch) {
    return wsRuntime.openWsAndAuth(epoch);
  }

  async function reconnectNow(epoch, reason) {
    return wsRuntime.reconnectNow(epoch, reason);
  }

  function considerAckCandidate(msgIdServer, sentAtMs) {
    messageRuntime.considerAckCandidate(msgIdServer, sentAtMs);
  }

  function scheduleAckFlush(reason, immediate) {
    messageRuntime.scheduleAckFlush(reason, immediate);
  }

  async function flushAck(reason) {
    return messageRuntime.flushAck(reason);
  }

  function markPendingStatus(pendingId, conversationId, status) {
    messageRuntime.markPendingStatus(pendingId, conversationId, status);
  }

  function promotePendingMessage(pendingId, conversationId, msgIdClient, msgIdServer, sentAtMs) {
    messageRuntime.promotePendingMessage(pendingId, conversationId, msgIdClient, msgIdServer, sentAtMs);
  }

  function createPendingMessage(conversationId, content, msgIdClient) {
    return messageRuntime.createPendingMessage(conversationId, content, msgIdClient);
  }

  function ingestTimelineMessage(message, source) {
    messageRuntime.ingestTimelineMessage(message, source);
  }

  async function loadContacts({ silent = false } = {}) {
    return contactsRuntime.loadContacts({ silent });
  }

  async function pullOffline({ reason = 'manual', silent = false } = {}) {
    return messageRuntime.pullOffline({ reason, silent });
  }

  async function activateAccount(accountId, reason) {
    return accountRuntime.activateAccount(accountId, reason);
  }

  async function loginAndAddAccount() {
    return accountRuntime.loginAndAddAccount();
  }

  async function switchAccount() {
    return accountRuntime.switchAccount();
  }

  async function forgetSelectedAccount() {
    return accountRuntime.forgetSelectedAccount();
  }

  async function sendManualAck() {
    return messageRuntime.sendManualAck();
  }

  async function fetchManualLlmRequestDetail() {
    return llmDebug.fetchManualLlmRequestDetail();
  }

  function scheduleAutoLlmDetailsRefresh() {
    llmDebug.scheduleAutoLlmDetailsRefresh();
  }

  function scheduleLlmLinkLookup() {
    llmDebug.scheduleLlmLinkLookup();
  }

  function scheduleTypingStartIfNeeded() {
    messageRuntime.scheduleTypingStartIfNeeded();
  }

  function cancelTypingStartBuffer() {
    messageRuntime.cancelTypingStartBuffer();
  }

  function stopTypingIfNeeded() {
    messageRuntime.stopTypingIfNeeded();
  }

  async function sendMessage() {
    return messageRuntime.sendMessage();
  }

  async function reconnectButtonAction() {
    return messageRuntime.reconnectButtonAction();
  }

  async function initialize() {
    if (!window.crypto || !window.crypto.subtle) {
      setStatus('当前环境不支持 Web Crypto API，聊天控制台无法安全启动。');
      appendLog('webcrypto_unavailable');
      updateControls();
      return;
    }

    setAuthBadge(false);
    setWsBadge(WS_BADGE.DISCONNECTED);
    setStage(STAGE.UNAUTH, '正在加载已保存会话...');
    resetSelfPanel();
    resetPeerPanel();
    resetSnapshotPanel();
    updateControls();

    await initializeLocalStorage();

    try {
      await loadVault();
      renderAccountSelect();
      appendLog({ vault_loaded_accounts: state.vault.accounts.length });
    } catch (err) {
      appendLog({ vault_load_error: String(err && err.message ? err.message : err) });
      state.vault = { accounts: [], active_account_id: null };
      renderAccountSelect();
    }

    if (state.vault.active_account_id) {
      try {
        await activateAccount(state.vault.active_account_id, 'restore');
        return;
      } catch (err) {
        appendLog({ restore_failed: String(err && err.message ? err.message : err) });
      }
    }

    setAuthBadge(false);
    setStage(STAGE.UNAUTH, '当前无活跃会话，请先登录后开始聊天。');
    updateControls();
  }

  function bindEvents() {
    bindChatConsoleEvents({
      el,
      state,
      STAGE,
      clearLog,
      openLoginModal,
      loginAndAddAccount,
      switchAccount,
      forgetSelectedAccount,
      reconnectButtonAction,
      loadContacts,
      setStage,
      appendLog,
      sendMessage,
      pullOffline,
      clearLocalMessagesForActiveAccount,
      setStatus,
      refreshInstanceSnapshot,
      wsSend,
      sendManualAck,
      fetchManualLlmRequestDetail,
      renderContacts,
      stopTypingIfNeeded,
      scheduleTypingStartIfNeeded,
      cancelTypingStartBuffer,
      closeLoginModal,
    });
  }

  bindEvents();
  void initialize();
})();
