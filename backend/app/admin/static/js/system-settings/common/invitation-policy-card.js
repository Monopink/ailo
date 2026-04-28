function t(i18n, key, fallback) {
  const value = i18n && Object.prototype.hasOwnProperty.call(i18n, key) ? i18n[key] : null;
  if (typeof value === 'string' && value.length > 0) {
    return value;
  }
  return fallback;
}

function setButtonLoading(button, loading, loadingHtml) {
  if (!button) {
    return () => {};
  }
  const originalHtml = button.innerHTML;
  const originalDisabled = button.disabled;
  if (loading) {
    button.disabled = true;
    button.innerHTML = loadingHtml;
  } else {
    button.disabled = originalDisabled;
    button.innerHTML = originalHtml;
  }
  return () => {
    button.disabled = originalDisabled;
    button.innerHTML = originalHtml;
  };
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  let data = null;
  try {
    data = await response.json();
  } catch (error) {
    data = null;
  }
  return { ok: response.ok, data };
}

export function initInvitationPolicyCard(config = {}) {
  const card = document.getElementById('invitation-policy-card');
  if (!card) {
    return;
  }
  const i18n = config.i18n || {};
  const api = config.api || {};
  const permissions = config.permissions || {};
  const canWriteInvitationPolicy = permissions.canWriteInvitationPolicy === true;
  const endpoint = api.invitationPolicy;
  if (!endpoint) {
    return;
  }

  const fields = {
    inviteeDelta: document.getElementById('ip-invitee-delta'),
    inviterDelta: document.getElementById('ip-inviter-delta'),
    inviterCap: document.getElementById('ip-inviter-cap'),
  };
  const saveButton = document.getElementById('save-invitation-policy-btn');
  const reloadButton = document.getElementById('reload-invitation-policy-btn');
  const editableInputs = [fields.inviteeDelta, fields.inviterDelta, fields.inviterCap];

  const applyReadOnlyState = () => {
    for (const input of editableInputs) {
      if (input) {
        input.disabled = !canWriteInvitationPolicy;
      }
    }
    if (saveButton) {
      saveButton.disabled = !canWriteInvitationPolicy;
      if (!canWriteInvitationPolicy) {
        saveButton.title = t(i18n, 'viewerReadOnly', 'Viewer can read but cannot save invitation policy.');
      }
    }
  };

  const applyPayload = (payload) => {
    fields.inviteeDelta.value = String(payload.invitee_reward_contact_delta ?? 0);
    fields.inviterDelta.value = String(payload.inviter_reward_contact_delta ?? 0);
    fields.inviterCap.value =
      payload.inviter_max_rewards_per_actor === null || payload.inviter_max_rewards_per_actor === undefined
        ? ''
        : String(payload.inviter_max_rewards_per_actor);
  };

  const collectPayload = () => {
    if (!canWriteInvitationPolicy) {
      throw new Error(t(i18n, 'viewerReadOnly', 'Viewer can read but cannot save invitation policy.'));
    }
    const inviteeDeltaRaw = Number.parseInt(String(fields.inviteeDelta.value || '0'), 10);
    const inviterDeltaRaw = Number.parseInt(String(fields.inviterDelta.value || '0'), 10);
    if (Number.isNaN(inviteeDeltaRaw) || inviteeDeltaRaw < 0) {
      throw new Error(t(i18n, 'invalidInviteeDelta', 'Invitee reward delta must be a non-negative integer.'));
    }
    if (Number.isNaN(inviterDeltaRaw) || inviterDeltaRaw < 0) {
      throw new Error(t(i18n, 'invalidInviterDelta', 'Inviter reward delta must be a non-negative integer.'));
    }
    const inviterCapRaw = String(fields.inviterCap.value || '').trim();
    let inviterCap = null;
    if (inviterCapRaw !== '') {
      const capParsed = Number.parseInt(inviterCapRaw, 10);
      if (Number.isNaN(capParsed) || capParsed < 1) {
        throw new Error(t(i18n, 'invalidInviterCap', 'Inviter reward cap must be empty or >= 1.'));
      }
      inviterCap = capParsed;
    }
    return {
      invitee_reward_contact_delta: inviteeDeltaRaw,
      inviter_reward_contact_delta: inviterDeltaRaw,
      inviter_max_rewards_per_actor: inviterCap,
    };
  };

  const loadPolicy = async () => {
    const restoreReloadBtn = setButtonLoading(
      reloadButton,
      true,
      '<span class="spinner-border spinner-border-sm me-1"></span>Reloading...'
    );
    try {
      const result = await fetchJson(endpoint);
      if (!result.ok || !result.data) {
        const detail =
          result.data && (result.data.detail || result.data.error)
            ? result.data.detail || result.data.error
            : t(i18n, 'loadPolicyFailed', 'Failed to load invitation policy');
        throw new Error(detail);
      }
      applyPayload(result.data);
    } finally {
      restoreReloadBtn();
    }
  };

  const savePolicy = async () => {
    const payload = collectPayload();
    const confirmed = window.confirm(t(i18n, 'savePolicyConfirm', 'Save invitation policy changes now?'));
    if (!confirmed) {
      return;
    }
    const restoreSaveBtn = setButtonLoading(
      saveButton,
      true,
      '<span class="spinner-border spinner-border-sm me-1"></span>Saving...'
    );
    try {
      const result = await fetchJson(endpoint, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!result.ok || !result.data || result.data.success !== true) {
        const detail =
          result.data && (result.data.detail || result.data.error)
            ? result.data.detail || result.data.error
            : t(i18n, 'savePolicyFailed', 'Failed to save invitation policy');
        throw new Error(detail);
      }
      window.alert(t(i18n, 'savePolicySuccess', 'Invitation policy saved'));
      await loadPolicy();
    } finally {
      restoreSaveBtn();
    }
  };

  if (reloadButton) {
    reloadButton.addEventListener('click', async () => {
      const confirmed = window.confirm(
        t(i18n, 'reloadPolicyConfirm', 'Reload policy values from server and discard unsaved card edits?')
      );
      if (!confirmed) {
        return;
      }
      try {
        await loadPolicy();
      } catch (error) {
        window.alert(
          error instanceof Error ? error.message : t(i18n, 'loadPolicyFailed', 'Failed to load invitation policy')
        );
      }
    });
  }

  if (saveButton) {
    if (canWriteInvitationPolicy) {
      saveButton.addEventListener('click', async () => {
        try {
          await savePolicy();
        } catch (error) {
          window.alert(
            error instanceof Error ? error.message : t(i18n, 'savePolicyFailed', 'Failed to save invitation policy')
          );
        }
      });
    }
  }

  applyReadOnlyState();

  loadPolicy().catch((error) => {
    window.alert(
      error instanceof Error ? error.message : t(i18n, 'loadPolicyFailed', 'Failed to load invitation policy')
    );
  });
}
