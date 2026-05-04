export function bindChatConsoleEvents({
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
}) {
  const dialogs = window.ailoDialogs;
  el.btnClearLog.addEventListener('click', clearLog);
  el.btnOpenLoginModal.addEventListener('click', () => {
    openLoginModal();
  });
  el.btnLogin.addEventListener('click', () => {
    void loginAndAddAccount();
  });
  el.btnSwitchAccount.addEventListener('click', () => {
    void switchAccount();
  });
  el.btnForgetAccount.addEventListener('click', () => {
    void (async () => {
      const accountId = el.accountSelect.value;
      if (!accountId) {
        return;
      }
      const selectedLabel = el.accountSelect.options[el.accountSelect.selectedIndex]?.text || accountId;
      const isActive = state.vault.active_account_id === accountId;
      const ok = await dialogs.confirm({
        title: '确认忘记账号',
        message: isActive
          ? `确认忘记当前活跃账号“${selectedLabel}”吗？<br>这会移除本地保存的登录态，并切换到其他账号或未登录状态。`
          : `确认忘记账号“${selectedLabel}”吗？<br>这会移除本地保存的登录态。`,
        confirmText: '忘记账号',
        cancelText: '取消',
        confirmButtonClass: 'btn btn-danger',
      });
      if (!ok) {
        return;
      }
      await forgetSelectedAccount();
    })();
  });
  el.btnReconnect.addEventListener('click', () => {
    void reconnectButtonAction();
  });
  el.btnRefreshContacts.addEventListener('click', () => {
    void (async () => {
      try {
        await loadContacts({ silent: false });
      } catch (err) {
        setStage(STAGE.DEGRADED, '刷新联系人失败。');
        appendLog({ contacts_refresh_failed: String(err && err.message ? err.message : err) });
      }
    })();
  });
  el.btnSend.addEventListener('click', () => {
    void sendMessage();
  });
  el.btnPullOffline.addEventListener('click', () => {
    void (async () => {
      try {
        await pullOffline({ reason: 'manual', silent: false });
      } catch (err) {
        setStage(STAGE.DEGRADED, '离线同步失败。');
        appendLog({ offline_manual_failed: String(err && err.message ? err.message : err) });
      }
    })();
  });
  el.btnClearLocal.addEventListener('click', () => {
    void (async () => {
      const ok = await dialogs.confirm({
        title: '确认清空本地缓存',
        message: '确认清空当前账号的本地缓存消息吗？<br>这不会删除服务端消息，但会移除当前浏览器中的本地缓存。',
        confirmText: '清空本地',
        cancelText: '取消',
        confirmButtonClass: 'btn btn-danger',
      });
      if (!ok) {
        return;
      }
      try {
        await clearLocalMessagesForActiveAccount();
      } catch (err) {
        appendLog({ clear_local_failed: String(err && err.message ? err.message : err) });
        setStatus('清空本地失败。');
      }
    })();
  });
  el.btnRefreshSnapshot.addEventListener('click', () => {
    void refreshInstanceSnapshot({ silent: false });
  });
  el.btnPing.addEventListener('click', () => {
    try {
      if (state.wsAuthed) {
        wsSend('ping', {}, 'ping');
        setStatus('心跳已发送。');
      }
    } catch (err) {
      appendLog({ ping_manual_failed: String(err && err.message ? err.message : err) });
    }
  });
  el.btnAck.addEventListener('click', () => {
    void sendManualAck();
  });
  el.btnLlmRequestDetail.addEventListener('click', () => {
    void fetchManualLlmRequestDetail();
  });

  el.contactSearch.addEventListener('input', () => {
    state.contactFilter = el.contactSearch.value || '';
    renderContacts();
  });

  el.messageInput.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      if (event.isComposing || event.keyCode === 229) {
        return;
      }
      event.preventDefault();
      void sendMessage();
    }
  });

  el.messageInput.addEventListener('compositionstart', () => {
    state.isMessageInputComposing = true;
    if (!state.wsAuthed || !state.selectedConversationId) {
      return;
    }
    const text = (el.messageInput.value || '').trim();
    if (!text) {
      scheduleTypingStartIfNeeded();
    }
  });

  el.messageInput.addEventListener('compositionend', () => {
    state.isMessageInputComposing = false;
    if (!state.wsAuthed || !state.selectedConversationId) {
      stopTypingIfNeeded();
      return;
    }
    const text = (el.messageInput.value || '').trim();
    if (!text) {
      stopTypingIfNeeded();
      return;
    }
    scheduleTypingStartIfNeeded();
  });

  el.messageInput.addEventListener('input', () => {
    if (!state.wsAuthed || !state.selectedConversationId) {
      stopTypingIfNeeded();
      return;
    }

    const text = (el.messageInput.value || '').trim();
    if (!text) {
      cancelTypingStartBuffer();
      if (!state.isMessageInputComposing) {
        stopTypingIfNeeded();
      }
      return;
    }

    scheduleTypingStartIfNeeded();
  });

  el.messageInput.addEventListener('blur', () => {
    state.isMessageInputComposing = false;
    stopTypingIfNeeded();
  });

  if (el.password) {
    el.password.addEventListener('keydown', (event) => {
      if (event.key !== 'Enter') {
        return;
      }
      event.preventDefault();
      void loginAndAddAccount();
    });
  }

  if (!window.bootstrap || !window.bootstrap.Modal) {
    for (const btn of document.querySelectorAll('#cc_login_modal [data-bs-dismiss="modal"]')) {
      btn.addEventListener('click', () => {
        closeLoginModal();
      });
    }
  }
}
