export function createAccountRuntimeController({
  el,
  state,
  api,
  STAGE,
  maxVaultAccounts,
  tokenRefreshSkewMs,
  vaultStorageKey,
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
}) {
  async function loadVault() {
    const raw = localStorage.getItem(vaultStorageKey);
    if (!raw) {
      state.vault = { accounts: [], active_account_id: null };
      return;
    }

    let encrypted = null;
    try {
      encrypted = JSON.parse(raw);
    } catch {
      appendLog('vault_parse_failed_reset');
      state.vault = { accounts: [], active_account_id: null };
      return;
    }

    try {
      const decoded = await decryptVaultPayload(encrypted);
      if (!decoded || typeof decoded !== 'object') {
        throw new Error('INVALID_VAULT_DECODED');
      }

      const normalizedAccounts = normalizeVaultAccounts(decoded.accounts, maxVaultAccounts);
      const activeId = resolveActiveAccountId(decoded.active_account_id, normalizedAccounts);

      state.vault = {
        accounts: normalizedAccounts,
        active_account_id: activeId,
      };
    } catch (err) {
      appendLog({ vault_decrypt_failed: String(err && err.message ? err.message : err) });
      state.vault = { accounts: [], active_account_id: null };
    }
  }

  async function saveVault() {
    const payload = {
      active_account_id: state.vault.active_account_id,
      accounts: state.vault.accounts.map((account) => ({
        account_id: account.account_id,
        user_qiao_id: account.user_qiao_id,
        identifier: account.identifier,
        device_id: account.device_id,
        refresh_token: account.refresh_token,
        access_token: account.access_token || '',
        expires_at_ms: account.expires_at_ms || 0,
        last_used_at_ms: account.last_used_at_ms || 0,
        user: account.user || {},
      })),
    };

    const encrypted = await encryptVaultPayload(payload);
    localStorage.setItem(vaultStorageKey, JSON.stringify(encrypted));
  }

  function replaceOrInsertAccount(nextAccount) {
    const idx = state.vault.accounts.findIndex((item) => item.account_id === nextAccount.account_id);
    if (idx >= 0) {
      state.vault.accounts[idx] = nextAccount;
    } else {
      state.vault.accounts.push(nextAccount);
    }

    state.vault.accounts.sort((a, b) => (b.last_used_at_ms || 0) - (a.last_used_at_ms || 0));
    if (state.vault.accounts.length > maxVaultAccounts) {
      state.vault.accounts = state.vault.accounts.slice(0, maxVaultAccounts);
    }
  }

  function getErrorMessage(err) {
    return String(err && err.message ? err.message : err || '');
  }

  function isAuthFailureError(err) {
    const message = getErrorMessage(err).toLowerCase();
    return (
      message.includes('auth_required') ||
      message.includes('token_refresh_failed') ||
      message.includes('session expired') ||
      message.includes('登录失效') ||
      message.includes('登录失败') ||
      message.includes('401')
    );
  }

  function removeAccount(accountId) {
    state.vault.accounts = state.vault.accounts.filter((item) => item.account_id !== accountId);
    if (!state.vault.accounts.length) {
      state.vault.active_account_id = null;
      return;
    }
    if (state.vault.active_account_id === accountId) {
      state.vault.active_account_id = state.vault.accounts[0].account_id;
    }
  }

  async function refreshAccessToken(account) {
    const res = await fetch('/api/v1/auth/refresh-token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: account.refresh_token }),
    });

    let json = null;
    try {
      json = await res.json();
    } catch {
      json = null;
    }

    if (!res.ok) {
      throw new Error(extractErrorMessage(json, res));
    }

    account.access_token = String(json.access_token || '');
    account.expires_at_ms = nowMs() + Number(json.expires_in || 0) * 1000;
    account.last_used_at_ms = nowMs();
    await saveVault();
    renderAccountSelect();
    renderSelfPanel(account);
  }

  async function ensureValidAccessToken(account, { force = false } = {}) {
    if (!account) {
      throw new Error('AUTH_REQUIRED');
    }
    const exp = Number(account.expires_at_ms || 0);
    if (!force && account.access_token && exp > nowMs() + tokenRefreshSkewMs) {
      return account.access_token;
    }
    await refreshAccessToken(account);
    if (!account.access_token) {
      throw new Error('TOKEN_REFRESH_FAILED');
    }
    return account.access_token;
  }

  async function fetchSelfProfile(account) {
    if (!account) return;
    try {
      const profile = await api('/api/v1/user/profile', { method: 'GET', auth: true });
      account.user = {
        ...(account.user || {}),
        qiao_id: profile && typeof profile.qiao_id === 'string' ? profile.qiao_id : account.user_qiao_id,
        username: profile && typeof profile.username === 'string' ? profile.username : '',
        nickname: profile && typeof profile.nickname === 'string' ? profile.nickname : '',
        avatar_url: profile && typeof profile.avatar_url === 'string' ? profile.avatar_url : '',
        bio: profile && typeof profile.bio === 'string' ? profile.bio : '',
        region: profile && typeof profile.region === 'string' ? profile.region : '',
        gender: profile ? profile.gender : null,
      };
      await saveVault();
      renderSelfPanel(account);
    } catch (err) {
      appendLog({ self_profile_failed: String(err && err.message ? err.message : err) });
    }
  }

  async function bootstrapActiveAccount(epoch, reason) {
    const account = getActiveAccount();
    if (!account) {
      setStage(STAGE.UNAUTH, '当前无活跃账号。');
      return;
    }

    setStage(STAGE.BOOTSTRAPPING, '正在启动聊天会话...');

    let contactsError = null;
    let offlineError = null;

    try {
      await ensureValidAccessToken(account, { force: false });
      await fetchSelfProfile(account);
      if (epoch !== currentEpoch()) return;

      await openWsAndAuth(epoch);
      if (epoch !== currentEpoch()) return;
      setAuthBadge(true);

      try {
        await loadContacts({ silent: true });
        if (state.selectedConversationId) {
          await hydrateConversationFromLocal(state.selectedConversationId, { forceBottom: true });
        }
      } catch (err) {
        contactsError = err;
        appendLog({ contacts_load_failed: String(err && err.message ? err.message : err) });
      }

      try {
        await pullOffline({ reason: `bootstrap:${reason}`, silent: true });
      } catch (err) {
        offlineError = err;
        appendLog({ offline_bootstrap_failed: String(err && err.message ? err.message : err) });
      }

      if (epoch !== currentEpoch()) return;

      if (!contactsError && !offlineError) {
        setStage(STAGE.READY, '就绪。');
      } else {
        setStage(STAGE.DEGRADED, '启动部分失败，可继续使用并重试相关工具。');
      }
    } catch (err) {
      if (epoch !== currentEpoch()) return;
      const errorMessage = getErrorMessage(err);
      appendLog({ bootstrap_failed: errorMessage });
      if (isAuthFailureError(err)) {
        closeWs({ suppressReconnect: true, reason: 'auth-expired' });
        setAuthBadge(false);
        setStage(STAGE.UNAUTH, '会话已过期，请重新登录。');
        return;
      }
      setStage(STAGE.RECONNECTING, '连接失败，正在自动重连...');
      scheduleReconnect('bootstrap-failed', epoch);
    }
  }

  function setActiveAccount(accountId) {
    state.vault.active_account_id = accountId;
    renderAccountSelect();
  }

  async function activateAccount(accountId, reason) {
    const account = state.vault.accounts.find((it) => it.account_id === accountId);
    if (!account) {
      throw new Error('ACCOUNT_NOT_FOUND');
    }

    const epoch = bumpEpoch();
    if (state.reconnectTimer) {
      window.clearTimeout(state.reconnectTimer);
      state.reconnectTimer = null;
    }
    state.reconnectAttempt = 0;

    closeWs({ suppressReconnect: true, reason: 'account-switch' });
    resetChatSurface();
    setActiveAccount(account.account_id);

    account.last_used_at_ms = nowMs();
    await saveVault();
    renderAccountSelect();
    renderSelfPanel(account);
    setAuthBadge(false);

    await bootstrapActiveAccount(epoch, reason);
  }

  async function loginAndAddAccount() {
    const identifier = (el.identifier.value || '').trim();
    const password = (el.password.value || '').trim();
    if (!identifier || !password) {
      setStatus('必须填写账户和密码。');
      return;
    }

    setStage(STAGE.AUTHING, '登录中...');
    const existing = state.vault.accounts.find((item) => item.identifier.toLowerCase() === identifier.toLowerCase());
    const deviceId = existing ? existing.device_id : makeDeviceId();

    try {
      const res = await api('/api/v1/auth/login', {
        method: 'POST',
        auth: false,
        body: {
          identifier,
          password,
          device_id: deviceId,
          device_type: 3,
        },
      });

      const user = res && res.user && typeof res.user === 'object' ? res.user : {};
      const userQiaoId = typeof user.qiao_id === 'string' ? user.qiao_id : '';
      if (!userQiaoId) {
        throw new Error('登录响应无效：缺少 user.qiao_id');
      }

      const account = {
        account_id: makeAccountId(userQiaoId, identifier),
        user_qiao_id: userQiaoId,
        identifier,
        device_id: deviceId,
        refresh_token: String(res.refresh_token || ''),
        access_token: String(res.access_token || ''),
        expires_at_ms: nowMs() + Number(res.expires_in || 0) * 1000,
        last_used_at_ms: nowMs(),
        user: {
          qiao_id: userQiaoId,
          username: typeof user.username === 'string' ? user.username : '',
          nickname: typeof user.nickname === 'string' ? user.nickname : '',
          avatar_url: typeof user.avatar_url === 'string' ? user.avatar_url : '',
          phone: typeof user.phone === 'string' ? user.phone : '',
          bio: typeof user.bio === 'string' ? user.bio : '',
          region: typeof user.region === 'string' ? user.region : '',
          gender: user.gender,
        },
      };

      replaceOrInsertAccount(account);
      state.vault.active_account_id = account.account_id;
      await saveVault();
      renderAccountSelect();
      renderSelfPanel(account);
      setAuthBadge(false);
      el.password.value = '';

      await activateAccount(account.account_id, 'login');
      closeLoginModal();
      appendLog({ login_ok: { user_qiao_id: userQiaoId, identifier } });
    } catch (err) {
      appendLog({ login_failed: String(err && err.message ? err.message : err) });
      setAuthBadge(Boolean(state.wsAuthed));
      setStage(hasSignedInAccount() ? STAGE.DEGRADED : STAGE.UNAUTH, '登录失败。');
    }
  }

  async function switchAccount() {
    const accountId = el.accountSelect.value;
    if (!accountId) {
      return;
    }
    setStage(STAGE.AUTHING, '正在切换账号...');
    try {
      await activateAccount(accountId, 'switch');
      appendLog({ account_switched: accountId });
    } catch (err) {
      appendLog({ account_switch_failed: getErrorMessage(err) });
      if (isAuthFailureError(err)) {
        setAuthBadge(false);
        setStage(STAGE.UNAUTH, '会话已过期，请重新登录。');
        return;
      }
      setStage(STAGE.DEGRADED, '切换账号失败。');
    }
  }

  async function forgetSelectedAccount() {
    const accountId = el.accountSelect.value;
    if (!accountId) {
      return;
    }
    const wasActive = state.vault.active_account_id === accountId;
    removeAccount(accountId);
    await saveVault();
    renderAccountSelect();

    if (!state.vault.accounts.length) {
      bumpEpoch();
      closeWs({ suppressReconnect: true, reason: 'forget-last-account' });
      resetChatSurface();
      resetSelfPanel();
      setAuthBadge(false);
      setStage(STAGE.UNAUTH, '已忘记该账号。');
      return;
    }

    if (wasActive) {
      try {
        await activateAccount(state.vault.active_account_id, 'forget-switch');
      } catch (err) {
        appendLog({ activate_after_forget_failed: String(err && err.message ? err.message : err) });
        setStage(STAGE.DEGRADED, '已忘记账号，但恢复当前活跃账号失败。');
      }
    } else {
      setStage(state.stage, '已忘记该账号。');
      updateControls();
    }
  }

  return Object.freeze({
    loadVault,
    saveVault,
    refreshAccessToken,
    ensureValidAccessToken,
    fetchSelfProfile,
    activateAccount,
    loginAndAddAccount,
    switchAccount,
    forgetSelectedAccount,
  });
}
