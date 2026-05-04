function applyTokens(template, values) {
  return String(template || '').replace(/\{(\w+)\}/g, (match, key) => {
    if (Object.prototype.hasOwnProperty.call(values, key)) {
      return String(values[key]);
    }
    return match;
  });
}

function setText(element, value) {
  if (!element) {
    return;
  }
  element.textContent = String(value);
}

class FieldValidationError extends Error {
  constructor(field, message) {
    super(message);
    this.name = 'FieldValidationError';
    this.field = field;
  }
}

function buildIdempotencyKey(entitlementTypeCode) {
  const normalized = String(entitlementTypeCode || 'unknown').trim() || 'unknown';
  return `admin_manual:${normalized}:${Date.now()}`;
}

function isDeltaValid(operationType, deltaValue) {
  if (operationType === 'grant') {
    return deltaValue > 0;
  }
  return deltaValue !== 0;
}

function formatSignedNumber(value) {
  const numericValue = Number.parseInt(String(value), 10);
  if (Number.isNaN(numericValue)) {
    return '-';
  }
  if (numericValue > 0) {
    return `+${numericValue}`;
  }
  return String(numericValue);
}

async function parseJsonResponse(response) {
  try {
    return await response.json();
  } catch (_error) {
    return {};
  }
}

async function initEntitlementOperationsPage(config) {
  const api = config.api || {};
  const i18n = config.i18n || {};
  const entitlementTypeLabels = config.entitlementTypeLabels || {};
  const reasonCodeMeta = config.reasonCodeMeta || {};

  const form = document.getElementById('entitlement-form');
  if (!form) {
    return;
  }

  const userIdEl = document.getElementById('user-id');
  const userAssetsPanelEl = document.getElementById('user-assets-panel');
  const userAssetsListEl = document.getElementById('user-assets-list');
  const entitlementTypeEl = document.getElementById('entitlement-type');
  const operationTypeInputs = Array.from(document.querySelectorAll("input[name='operation-type']"));
  const deltaEl = document.getElementById('delta');
  const deltaPanelEl = document.getElementById('delta-panel');
  const afterPanelEl = document.getElementById('after-panel');
  const deltaValidationHintEl = document.getElementById('delta-validation-hint');
  const reasonCodeEl = document.getElementById('reason-code');
  const reasonCodeValidationHintEl = document.getElementById('reason-code-validation-hint');
  const remarkEl = document.getElementById('remark');
  const idempotencyKeyEl = document.getElementById('idempotency-key');
  const submitBtn = document.getElementById('submit-btn');
  const currentAvailableEl = document.getElementById('current-available-total');
  const previewAvailableEl = document.getElementById('preview-available-total');
  const resultInlineEl = document.getElementById('result-inline');
  const resultAlert = document.getElementById('operation-feedback-alert');
  const resultIconEl = document.getElementById('operation-feedback-icon');
  const resultTitleEl = document.getElementById('operation-feedback-title');
  const resultBodyEl = document.getElementById('operation-feedback-body');

  const confirmModalEl = document.getElementById('operation-confirm-modal');
  const confirmExecuteBtn = document.getElementById('confirm-execute-btn');
  const confirmUserEl = document.getElementById('confirm-user');
  const confirmTypeEl = document.getElementById('confirm-type');
  const confirmOperationEl = document.getElementById('confirm-operation');
  const confirmReasonEl = document.getElementById('confirm-reason');
  const confirmOriginalEl = document.getElementById('confirm-original');
  const confirmDeltaEl = document.getElementById('confirm-delta');
  const confirmAfterEl = document.getElementById('confirm-after');

  const bootstrapModal =
    typeof window !== 'undefined' && window.bootstrap && confirmModalEl && typeof window.bootstrap.Modal === 'function'
      ? new window.bootstrap.Modal(confirmModalEl)
      : null;

  const reasonCodeOptions = Object.entries(reasonCodeMeta).map(([code, meta]) => {
    const typedMeta = meta || {};
    return {
      code: String(code),
      displayName: String(typedMeta.display_name || code),
      appliesTo: String(typedMeta.applies_to || 'both').toLowerCase(),
    };
  });

  let currentSnapshot = null;
  let pendingDraft = null;

  function getSelectedOperationType() {
    const selected = operationTypeInputs.find((item) => item.checked);
    return selected ? String(selected.value || '') : 'grant';
  }

  function reasonCodeSupportsOperation(appliesTo, operationType) {
    return appliesTo === 'both' || appliesTo === operationType;
  }

  function setDeltaValidationState(isInvalid, message = '') {
    deltaPanelEl?.classList.toggle('is-invalid', Boolean(isInvalid));
    afterPanelEl?.classList.toggle('is-invalid', Boolean(isInvalid));
    previewAvailableEl?.classList.toggle('is-invalid', Boolean(isInvalid));
    deltaEl?.classList.toggle('is-invalid', Boolean(isInvalid));
    if (!deltaValidationHintEl) {
      return;
    }
    if (isInvalid) {
      deltaValidationHintEl.classList.remove('d-none');
      deltaValidationHintEl.textContent = String(message || i18n.invalidResultInline || '');
      return;
    }
    deltaValidationHintEl.classList.add('d-none');
    deltaValidationHintEl.textContent = '';
  }

  function setReasonCodeValidationState(isInvalid, message = '') {
    reasonCodeEl?.classList.toggle('is-invalid', Boolean(isInvalid));
    if (!reasonCodeValidationHintEl) {
      return;
    }
    if (isInvalid) {
      reasonCodeValidationHintEl.classList.remove('d-none');
      reasonCodeValidationHintEl.textContent = String(message || i18n.selectReasonCode || '');
      return;
    }
    reasonCodeValidationHintEl.classList.add('d-none');
    reasonCodeValidationHintEl.textContent = '';
  }

  function renderReasonCodeOptions(operationType, preferredCode = '') {
    if (!reasonCodeEl) {
      return;
    }

    const sourceOptions = reasonCodeOptions.length > 0 ? reasonCodeOptions : [];
    const availableOptions = sourceOptions.filter((option) =>
      reasonCodeSupportsOperation(option.appliesTo, operationType)
    );

    reasonCodeEl.innerHTML = '';
    const defaultOption = document.createElement('option');
    defaultOption.value = '';
    defaultOption.textContent = i18n.selectReasonCodePrompt || '';
    reasonCodeEl.appendChild(defaultOption);

    if (availableOptions.length === 0) {
      defaultOption.textContent = i18n.noReasonCodeForOperation || '';
      reasonCodeEl.disabled = true;
      setReasonCodeValidationState(false);
      return;
    }

    reasonCodeEl.disabled = false;
    for (const option of availableOptions) {
      const element = document.createElement('option');
      element.value = option.code;
      element.textContent = `${option.displayName} (${option.code})`;
      reasonCodeEl.appendChild(element);
    }

    const targetValue =
      preferredCode && availableOptions.some((item) => item.code === preferredCode) ? preferredCode : '';
    reasonCodeEl.value = targetValue;
    setReasonCodeValidationState(false);
  }

  function updateIdempotencyKey() {
    if (!idempotencyKeyEl || !entitlementTypeEl) {
      return;
    }
    idempotencyKeyEl.value = buildIdempotencyKey(entitlementTypeEl.value);
  }

  function renderPreviewAvailable(showValidation = false) {
    if (!previewAvailableEl || !deltaEl) {
      return;
    }
    if (!currentSnapshot) {
      setDeltaValidationState(false);
      setText(previewAvailableEl, '-');
      return;
    }

    const delta = Number.parseInt(String(deltaEl.value || ''), 10);
    if (Number.isNaN(delta)) {
      setDeltaValidationState(showValidation, i18n.invalidResultInline);
      setText(previewAvailableEl, '-');
      return;
    }

    const operationType = getSelectedOperationType();
    if (!isDeltaValid(operationType, delta)) {
      setDeltaValidationState(showValidation, i18n.invalidResultInline);
      setText(previewAvailableEl, '-');
      return;
    }

    const nextAvailable = Number(currentSnapshot.available_total) + delta;
    if (nextAvailable < 0) {
      setDeltaValidationState(showValidation, i18n.invalidResultInline);
      setText(previewAvailableEl, '-');
      return;
    }

    setDeltaValidationState(false);
    setText(previewAvailableEl, nextAvailable);
  }

  function renderCurrentAvailable(snapshot) {
    currentSnapshot = snapshot;
    if (!snapshot) {
      setText(currentAvailableEl, '-');
      renderPreviewAvailable();
      return;
    }
    setText(currentAvailableEl, snapshot.available_total);
    renderPreviewAvailable();
  }

  function clearUserAssets() {
    if (userAssetsListEl) {
      userAssetsListEl.innerHTML = '';
    }
    userAssetsPanelEl?.classList.add('d-none');
  }

  function renderUserAssets(items) {
    if (!userAssetsListEl || !userAssetsPanelEl) {
      return;
    }

    userAssetsListEl.innerHTML = '';
    if (!Array.isArray(items) || items.length === 0) {
      userAssetsPanelEl.classList.add('d-none');
      return;
    }

    for (const item of items) {
      const code = String(item.entitlement_type_code || '');
      const displayName = String(entitlementTypeLabels[code] || code);
      const available = Number.parseInt(String(item.available_total || 0), 10);
      const granted = Number.parseInt(String(item.granted_total || 0), 10);
      const used = Number.parseInt(String(item.used_total || 0), 10);

      const rowEl = document.createElement('div');
      rowEl.className = 'ops-asset-item';

      const titleEl = document.createElement('div');
      titleEl.className = 'ops-asset-title';
      titleEl.textContent = `${displayName}:`;

      const valueEl = document.createElement('div');
      valueEl.className = 'ops-asset-value';
      valueEl.textContent = `${i18n.assetAvailableLabel}: ${available} | ${i18n.assetGrantedLabel}: ${granted} | ${i18n.assetUsedLabel}: ${used}`;

      rowEl.appendChild(titleEl);
      rowEl.appendChild(valueEl);
      userAssetsListEl.appendChild(rowEl);
    }

    userAssetsPanelEl.classList.remove('d-none');
  }

  function showResult({ success, title, body }) {
    if (!resultInlineEl || !resultAlert) {
      return;
    }

    resultInlineEl.classList.remove('d-none');
    resultAlert.classList.remove('alert-success', 'alert-warning', 'alert-danger');
    resultAlert.classList.add(success ? 'alert-success' : 'alert-danger');
    if (resultIconEl) {
      resultIconEl.className = success
        ? 'ops-result-icon fa fa-check-circle'
        : 'ops-result-icon fa fa-exclamation-triangle';
    }
    setText(resultTitleEl, title);
    setText(resultBodyEl, body);
  }

  async function loadAccountSnapshot() {
    if (!userIdEl || !entitlementTypeEl) {
      return;
    }

    const userId = String(userIdEl.value || '').trim();
    const entitlementTypeCode = String(entitlementTypeEl.value || '').trim();
    if (userId === '' || entitlementTypeCode === '') {
      renderCurrentAvailable(null);
      return;
    }

    const url = `${api.accountSnapshot}?user_id=${encodeURIComponent(
      userId
    )}&entitlement_type_code=${encodeURIComponent(entitlementTypeCode)}`;
    const response = await fetch(url, { credentials: 'same-origin' });
    const data = await parseJsonResponse(response);
    if (!response.ok) {
      throw new Error(data.detail || i18n.snapshotLoadFailed);
    }
    renderCurrentAvailable(data);
  }

  async function loadUserAssets() {
    if (!userIdEl || !api.userAssets) {
      return;
    }

    const selectedUserId = String(userIdEl.value || '').trim();
    if (selectedUserId === '') {
      clearUserAssets();
      return;
    }

    const response = await fetch(`${api.userAssets}?user_id=${encodeURIComponent(selectedUserId)}`, {
      credentials: 'same-origin',
    });
    const data = await parseJsonResponse(response);
    if (!response.ok) {
      throw new Error(data.detail || i18n.userAssetsLoadFailed);
    }
    renderUserAssets(Array.isArray(data.items) ? data.items : []);
  }

  async function refreshUserPanels() {
    await Promise.all([loadAccountSnapshot(), loadUserAssets()]);
  }

  function buildOperationDraft() {
    if (!userIdEl || !entitlementTypeEl || !deltaEl || !reasonCodeEl) {
      return null;
    }

    const selectedUserId = String(userIdEl.value || '').trim();
    if (selectedUserId === '') {
      throw new Error(i18n.selectUserFirst);
    }

    const operationType = getSelectedOperationType();
    const selectedReasonCode = String(reasonCodeEl.value || '').trim();
    if (selectedReasonCode === '' || reasonCodeEl.disabled) {
      const reasonMessage = reasonCodeEl.disabled
        ? i18n.noReasonCodeForOperation || i18n.submitFailed
        : i18n.selectReasonCode || i18n.submitFailed;
      setReasonCodeValidationState(true, reasonMessage);
      throw new FieldValidationError('reason-code', reasonMessage);
    }
    setReasonCodeValidationState(false);

    const delta = Number.parseInt(String(deltaEl.value || ''), 10);
    if (Number.isNaN(delta) || !isDeltaValid(operationType, delta)) {
      throw new Error(i18n.invalidDeltaPreview || i18n.invalidResult);
    }

    if (!currentSnapshot) {
      throw new Error(i18n.snapshotLoadFailed);
    }

    const nextAvailable = Number(currentSnapshot.available_total) + delta;
    if (nextAvailable < 0) {
      throw new Error(i18n.invalidResult);
    }

    const selectedUserLabel = String(userIdEl.options[userIdEl.selectedIndex]?.textContent || selectedUserId);
    const entitlementTypeCode = String(entitlementTypeEl.value || '');
    const entitlementTypeLabel = String(entitlementTypeLabels[entitlementTypeCode] || entitlementTypeCode);
    const operationLabel = operationType === 'grant' ? i18n.operationTypeGrant : i18n.operationTypeAdjust;
    const reasonLabel = String(reasonCodeEl.options[reasonCodeEl.selectedIndex]?.textContent || selectedReasonCode);

    const remarkValue = String(remarkEl?.value || '').trim();
    const payload = {
      user_id: selectedUserId,
      entitlement_type_code: entitlementTypeCode,
      operation_type: operationType,
      delta,
      reason_code: selectedReasonCode,
      idempotency_key: idempotencyKeyEl.value,
      remark: remarkValue === '' ? null : remarkValue,
    };

    return {
      payload,
      preview: {
        user: selectedUserLabel,
        type: entitlementTypeLabel,
        operation: operationLabel,
        reason: reasonLabel,
        original: Number(currentSnapshot.available_total),
        delta,
        next: nextAvailable,
      },
    };
  }

  function openConfirmDialog(draft) {
    if (!draft) {
      return;
    }

    setText(confirmUserEl, draft.preview.user);
    setText(confirmTypeEl, draft.preview.type);
    setText(confirmOperationEl, draft.preview.operation);
    setText(confirmReasonEl, draft.preview.reason);
    setText(confirmOriginalEl, draft.preview.original);
    setText(confirmDeltaEl, formatSignedNumber(draft.preview.delta));
    setText(confirmAfterEl, draft.preview.next);

    pendingDraft = draft;

    if (bootstrapModal) {
      bootstrapModal.show();
      return;
    }

    const confirmMessage = `${i18n.confirmOperationBody}\n${draft.preview.user}\n${draft.preview.type}\n${
      draft.preview.operation
    }\n${formatSignedNumber(draft.preview.delta)} => ${draft.preview.next}`;
    if (window.confirm(confirmMessage)) {
      executeOperation();
    }
  }

  async function executeOperation() {
    if (!pendingDraft) {
      return;
    }

    submitBtn.disabled = true;
    if (confirmExecuteBtn) {
      confirmExecuteBtn.disabled = true;
    }

    try {
      const response = await fetch(api.operations, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify(pendingDraft.payload),
      });
      const data = await parseJsonResponse(response);
      if (!response.ok) {
        throw new Error(data.detail || i18n.submitFailed);
      }

      const operationTitle = data.applied ? i18n.operationSucceeded : i18n.operationDuplicated;
      const summaryLine = applyTokens(i18n.resultSummary, {
        user: data.user_id,
        type: pendingDraft.preview.type,
        operation: pendingDraft.preview.operation,
        delta: formatSignedNumber(data.delta_granted),
      });
      const availableLine = applyTokens(i18n.resultAvailable, {
        available: data.available_total,
      });
      showResult({
        success: true,
        title: operationTitle,
        body: `${summaryLine} ${availableLine}`,
      });

      if (
        typeof data.available_total === 'number' &&
        typeof data.granted_total === 'number' &&
        typeof data.used_total === 'number'
      ) {
        renderCurrentAvailable({
          available_total: data.available_total,
          granted_total: data.granted_total,
          used_total: data.used_total,
        });
      } else {
        await loadAccountSnapshot();
      }

      await loadUserAssets();
      updateIdempotencyKey();
    } catch (error) {
      showResult({
        success: false,
        title: i18n.submitFailed,
        body: String(error?.message || error),
      });
    } finally {
      pendingDraft = null;
      if (bootstrapModal) {
        bootstrapModal.hide();
      }
      submitBtn.disabled = false;
      if (confirmExecuteBtn) {
        confirmExecuteBtn.disabled = false;
      }
    }
  }

  function submitOperation(event) {
    event.preventDefault();
    try {
      const draft = buildOperationDraft();
      openConfirmDialog(draft);
    } catch (error) {
      if (error instanceof FieldValidationError) {
        return;
      }
      showResult({
        success: false,
        title: i18n.submitFailed,
        body: String(error?.message || error),
      });
    }
  }

  function initializeUserSelect2() {
    if (!userIdEl) {
      return;
    }
    const searchSelect = window.ailoSearchSelect;
    if (!searchSelect || typeof searchSelect.initSearchSelect !== 'function') {
      return;
    }
    searchSelect.initSearchSelect({
      element: userIdEl,
      searchUrl: String(api.userSearch || ''),
      placeholder: String(userIdEl.dataset.placeholder || i18n.selectUserPrompt || ''),
      minimumInputLength: 1,
      limit: 20,
      allowClear: true,
      language: {
        inputTooShort: i18n.selectUserPrompt || '',
        noResults: i18n.noSearchResult || '',
        searching: i18n.searchingUsers || '',
        errorLoading: i18n.searchFailed || '',
      },
      onSelect: () => {
        refreshUserPanels().catch((error) => {
          showResult({
            success: false,
            title: i18n.snapshotLoadFailed,
            body: String(error?.message || i18n.snapshotLoadFailed),
          });
        });
      },
      onClear: () => {
        renderCurrentAvailable(null);
        clearUserAssets();
      },
    });
  }

  updateIdempotencyKey();
  renderCurrentAvailable(null);
  clearUserAssets();
  setDeltaValidationState(false);
  renderReasonCodeOptions(getSelectedOperationType(), String(reasonCodeEl?.value || ''));

  initializeUserSelect2();

  entitlementTypeEl?.addEventListener('change', () => {
    updateIdempotencyKey();
    loadAccountSnapshot().catch((error) => {
      showResult({
        success: false,
        title: i18n.snapshotLoadFailed,
        body: String(error?.message || i18n.snapshotLoadFailed),
      });
    });
    loadUserAssets().catch(() => {
      clearUserAssets();
    });
  });

  for (const operationTypeInput of operationTypeInputs) {
    operationTypeInput.addEventListener('change', () => {
      const previousReasonCode = String(reasonCodeEl?.value || '');
      renderReasonCodeOptions(getSelectedOperationType(), previousReasonCode);
      renderPreviewAvailable();
    });
  }

  deltaEl?.addEventListener('input', () => {
    renderPreviewAvailable(false);
  });
  deltaEl?.addEventListener('blur', () => {
    renderPreviewAvailable(true);
  });

  reasonCodeEl?.addEventListener('change', () => {
    const selectedReasonCode = String(reasonCodeEl.value || '').trim();
    if (reasonCodeEl.disabled) {
      setReasonCodeValidationState(false);
      return;
    }
    setReasonCodeValidationState(selectedReasonCode === '', i18n.selectReasonCode || '');
  });

  confirmExecuteBtn?.addEventListener('click', () => {
    executeOperation().catch((error) => {
      showResult({
        success: false,
        title: i18n.submitFailed,
        body: String(error?.message || error),
      });
    });
  });

  form.addEventListener('submit', submitOperation);

  if (String(userIdEl?.value || '').trim() !== '') {
    refreshUserPanels().catch(() => {
      renderCurrentAvailable(null);
      clearUserAssets();
    });
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const config = window.ailoEntitlementOperationsPageConfig || {};
  initEntitlementOperationsPage(config);
});
