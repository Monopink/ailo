import { mountRowAction } from '../components/list-row-action-injector.js';
import { createConfirmActionModal } from '../components/confirm-action-modal.js';
import { createPageFeedback } from '../components/page-feedback.js';

const config = window.ailoSecurityIpBlockListConfig || {};
const api = config.api || {};
const i18n = config.i18n || {};
const blockReasonPresets = Array.isArray(config.blockReasonPresets)
  ? config.blockReasonPresets
      .filter((item) => typeof item === 'string')
      .map((item) => item.trim())
      .filter((item) => item !== '')
  : [];
const releaseReasonPresets = Array.isArray(config.releaseReasonPresets)
  ? config.releaseReasonPresets
      .filter((item) => typeof item === 'string')
      .map((item) => item.trim())
      .filter((item) => item !== '')
  : [];
const CUSTOM_REASON_VALUE = '__custom__';
const feedback = createPageFeedback({ containerId: 'security-ip-block-list-feedback' });

const isTruthy = (value) => value === true;

const parseJsonSafe = async (response) => {
  try {
    return await response.json();
  } catch {
    return {};
  }
};

const toErrorMessage = (error, fallback) => {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  if (typeof error === 'string' && error.trim() !== '') {
    return error;
  }
  return fallback;
};

const showError = (message) => {
  feedback.error(message || i18n.operationFailed || 'Operation failed');
};

const showSuccess = (message) => {
  feedback.success(message || '');
};

const escapeHtml = (value) =>
  String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');

const requiredLabel = (label) => `${label} <span class="text-danger">*</span>`;

const isValidIPv4 = (value) => {
  const parts = value.split('.');
  if (parts.length !== 4) {
    return false;
  }
  for (const part of parts) {
    if (!/^\d{1,3}$/.test(part)) {
      return false;
    }
    if (part.length > 1 && part.startsWith('0')) {
      return false;
    }
    const num = Number.parseInt(part, 10);
    if (!Number.isFinite(num) || num < 0 || num > 255) {
      return false;
    }
  }
  return true;
};

const isValidIPv6 = (value) => {
  // Supports standard and compressed IPv6 forms.
  return /^(([0-9A-Fa-f]{1,4}:){7}[0-9A-Fa-f]{1,4}|(([0-9A-Fa-f]{1,4}:){1,7}:)|(:([0-9A-Fa-f]{1,4}:){1,7})|(([0-9A-Fa-f]{1,4}:){1,6}:[0-9A-Fa-f]{1,4})|(([0-9A-Fa-f]{1,4}:){1,5}(:[0-9A-Fa-f]{1,4}){1,2})|(([0-9A-Fa-f]{1,4}:){1,4}(:[0-9A-Fa-f]{1,4}){1,3})|(([0-9A-Fa-f]{1,4}:){1,3}(:[0-9A-Fa-f]{1,4}){1,4})|(([0-9A-Fa-f]{1,4}:){1,2}(:[0-9A-Fa-f]{1,4}){1,5})|([0-9A-Fa-f]{1,4}:((:[0-9A-Fa-f]{1,4}){1,6}))|(:((:[0-9A-Fa-f]{1,4}){1,7}|:)))$/.test(
    value
  );
};

const getIpVersion = (value) => {
  if (isValidIPv4(value)) {
    return 4;
  }
  if (isValidIPv6(value)) {
    return 6;
  }
  return null;
};

const validateTargetFormat = (target) => {
  const rawTarget = String(target || '').trim();
  if (rawTarget === '') {
    return { ok: false, code: 'empty' };
  }

  if (rawTarget.includes('/')) {
    const [ipPartRaw, prefixRaw] = rawTarget.split('/');
    const ipPart = String(ipPartRaw || '').trim();
    const prefix = String(prefixRaw || '').trim();
    if (ipPart === '' || prefix === '' || rawTarget.split('/').length !== 2) {
      return { ok: false, code: 'cidr' };
    }
    if (!/^\d{1,3}$/.test(prefix)) {
      return { ok: false, code: 'cidr' };
    }
    const version = getIpVersion(ipPart);
    if (version === null) {
      return { ok: false, code: 'cidr' };
    }
    const prefixNum = Number.parseInt(prefix, 10);
    const maxPrefix = version === 4 ? 32 : 128;
    if (!Number.isFinite(prefixNum) || prefixNum < 0 || prefixNum > maxPrefix) {
      return { ok: false, code: 'cidr' };
    }
    return { ok: true };
  }

  if (getIpVersion(rawTarget) !== null) {
    return { ok: true };
  }
  return { ok: false, code: 'ip' };
};

const createReasonPresetOptions = ({ presets, placeholder, customOption }) => {
  const options = [`<option value="">${escapeHtml(placeholder || 'Select a reason')}</option>`];
  presets.forEach((item) => {
    options.push(`<option value="${escapeHtml(item)}">${escapeHtml(item)}</option>`);
  });
  options.push(`<option value="${CUSTOM_REASON_VALUE}">${escapeHtml(customOption || 'Custom')}</option>`);
  return options.join('');
};

const parseEvidencePayload = (rawPayload) => {
  if (rawPayload && typeof rawPayload === 'object') {
    return rawPayload;
  }
  if (typeof rawPayload !== 'string') {
    return null;
  }
  try {
    const parsed = JSON.parse(rawPayload);
    if (parsed && typeof parsed === 'object') {
      return parsed;
    }
  } catch {
    return null;
  }
  return null;
};

const getBlockedReasonText = (rowData) => {
  const evidencePayload = parseEvidencePayload(rowData?.evidence_payload);
  const manualReason =
    evidencePayload && typeof evidencePayload.manual_reason === 'string' ? evidencePayload.manual_reason.trim() : '';
  if (manualReason !== '') {
    return manualReason;
  }
  const reasonCode = String(rowData?.reason_code || '').trim();
  return reasonCode === '' ? '-' : reasonCode;
};

const getSeverityText = (severityRaw) => {
  const severity = Number.parseInt(String(severityRaw || ''), 10);
  if (severity === 1) {
    return i18n.severityLow || 'LOW';
  }
  if (severity === 2) {
    return i18n.severityMedium || 'MEDIUM';
  }
  if (severity === 3) {
    return i18n.severityHigh || 'HIGH';
  }
  if (severity === 4) {
    return i18n.severityCritical || 'CRITICAL';
  }
  return String(severityRaw || '-');
};

const createModal = () => {
  const modalHtml = `
    <div class="modal fade" id="security-ip-block-op-modal" tabindex="-1" aria-hidden="true">
      <div class="modal-dialog modal-dialog-centered">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title" id="security-ip-block-op-modal-title"></h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="${
              i18n.cancel || 'Cancel'
            }"></button>
          </div>
          <div class="modal-body">
            <div id="security-ip-block-op-modal-body"></div>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">${
              i18n.cancel || 'Cancel'
            }</button>
            <button type="button" class="btn btn-primary" id="security-ip-block-op-submit">${
              i18n.confirm || 'Confirm'
            }</button>
          </div>
        </div>
      </div>
    </div>`;
  const wrapper = document.createElement('div');
  wrapper.innerHTML = modalHtml;
  document.body.appendChild(wrapper.firstElementChild);
};

const getModalElements = () => {
  const modalEl = document.getElementById('security-ip-block-op-modal');
  const titleEl = document.getElementById('security-ip-block-op-modal-title');
  const bodyEl = document.getElementById('security-ip-block-op-modal-body');
  const submitEl = document.getElementById('security-ip-block-op-submit');
  const modal =
    typeof window !== 'undefined' && window.bootstrap && modalEl && typeof window.bootstrap.Modal === 'function'
      ? new window.bootstrap.Modal(modalEl)
      : null;
  return {
    modal,
    titleEl,
    bodyEl,
    submitEl,
  };
};

const createAddBlockForm = () => {
  const reasonPresetOptions = createReasonPresetOptions({
    presets: blockReasonPresets,
    placeholder: i18n.reasonPresetPlaceholder || 'Select a reason',
    customOption: i18n.reasonCustomOption || 'Custom',
  });
  return `
    <div class="mb-3">
      <label class="form-label">${requiredLabel(i18n.targetLabel || 'Target')}</label>
      <input class="form-control" id="ip-block-target-value" maxlength="64" placeholder="203.0.113.7 or 203.0.113.0/24" />
    </div>
    <div class="mb-3">
      <label class="form-label">${requiredLabel(i18n.severityLabel || 'Severity')}</label>
      <select class="form-select" id="ip-block-severity-level">
        <option value="2">2 - medium</option>
        <option value="3" selected>3 - high</option>
        <option value="4">4 - critical</option>
        <option value="1">1 - low</option>
      </select>
    </div>
    <div class="mb-3">
      <label class="form-label">${requiredLabel(i18n.reasonLabel || 'Reason')}</label>
      <select class="form-select" id="ip-block-reason-preset">${reasonPresetOptions}</select>
      <div class="mt-2 d-none" id="ip-block-reason-custom-group">
        <label class="form-label mb-1">${requiredLabel(i18n.reasonCustomLabel || 'Custom Reason')}</label>
        <input class="form-control" id="ip-block-reason-custom" maxlength="500" />
      </div>
    </div>
    <div class="mb-3">
      <label class="form-label">${requiredLabel(i18n.blockModeLabel || 'Block Mode')}</label>
      <div class="btn-group w-100" role="group" aria-label="Block mode toggle">
        <input type="radio" class="btn-check" name="ip-block-mode" id="ip-block-mode-temporary" autocomplete="off" checked />
        <label class="btn btn-outline-primary" for="ip-block-mode-temporary">${
          i18n.temporaryMode || 'Temporary'
        }</label>
        <input type="radio" class="btn-check" name="ip-block-mode" id="ip-block-mode-permanent" autocomplete="off" />
        <label class="btn btn-outline-primary" for="ip-block-mode-permanent">${
          i18n.permanentMode || 'Permanent'
        }</label>
      </div>
    </div>
    <div class="mb-1" id="ip-block-ttl-group">
      <label class="form-label">${requiredLabel(i18n.ttlLabel || 'TTL Seconds')}</label>
      <input class="form-control" id="ip-block-ttl-seconds" type="number" min="1" step="1" value="3600" />
    </div>`;
};

const injectAddBlockButton = (openAddBlockModal) => {
  const container = document.querySelector('.card-actions .btn-list') || document.getElementById('btn_container');
  if (!container || container.querySelector('.js-add-ip-block-btn')) {
    return;
  }
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'btn btn-primary js-add-ip-block-btn ms-2';
  button.innerHTML = `<i class="fa-solid fa-plus me-2"></i>${i18n.addBlock || 'Add Block'}`;
  button.addEventListener('click', openAddBlockModal);
  container.appendChild(button);
};

const toBoolean = (value) => {
  if (value === true || value === 1) {
    return true;
  }
  if (typeof value === 'string') {
    const normalized = value.trim().toLowerCase();
    return normalized === 'true' || normalized === '1' || normalized === 'yes';
  }
  return false;
};

const isRowReleasable = (rowData) => {
  const statusText = String(rowData?.status || '')
    .trim()
    .toLowerCase();
  const statusActive = statusText === 'active' || statusText === '1';
  return statusActive && toBoolean(rowData?.is_effective);
};

const initPage = async () => {
  if (!isTruthy(config.canOperate)) {
    return;
  }
  createModal();
  const { modal, titleEl, bodyEl, submitEl } = getModalElements();
  if (!modal || !titleEl || !bodyEl || !submitEl) {
    return;
  }
  const confirmModal = createConfirmActionModal({
    modalId: 'security-release-confirm-modal',
    cancelText: i18n.cancel || 'Cancel',
    defaultErrorMessage: i18n.operationFailed || 'Operation failed',
    showAlert: showError,
    reloadOnSuccess: true,
  });

  let submitHandler = null;

  const bindSubmitHandler = (handler) => {
    submitHandler = handler;
  };

  submitEl.addEventListener('click', async () => {
    if (typeof submitHandler !== 'function') {
      return;
    }
    submitEl.disabled = true;
    try {
      await submitHandler();
      modal.hide();
      window.location.reload();
    } catch (error) {
      showError(toErrorMessage(error, i18n.operationFailed || 'Operation failed'));
    } finally {
      submitEl.disabled = false;
    }
  });

  const openAddBlockModal = () => {
    titleEl.textContent = i18n.addBlock || 'Add Block';
    bodyEl.innerHTML = createAddBlockForm();
    const permanentEl = document.getElementById('ip-block-mode-permanent');
    const ttlGroupEl = document.getElementById('ip-block-ttl-group');
    const ttlEl = document.getElementById('ip-block-ttl-seconds');
    const reasonPresetEl = document.getElementById('ip-block-reason-preset');
    const reasonCustomGroupEl = document.getElementById('ip-block-reason-custom-group');
    const reasonCustomEl = document.getElementById('ip-block-reason-custom');
    const syncTtlVisibility = () => {
      const permanent = Boolean(permanentEl?.checked);
      ttlGroupEl?.classList.toggle('d-none', permanent);
      if (ttlEl && ttlEl.tagName === 'INPUT') {
        ttlEl.disabled = permanent;
      }
    };
    const syncReasonCustomVisibility = () => {
      const isCustom = String(reasonPresetEl?.value || '') === CUSTOM_REASON_VALUE;
      reasonCustomGroupEl?.classList.toggle('d-none', !isCustom);
      if (reasonCustomEl && reasonCustomEl.tagName === 'INPUT') {
        reasonCustomEl.disabled = !isCustom;
      }
    };
    document.querySelectorAll('input[name="ip-block-mode"]').forEach((element) => {
      element.addEventListener('change', syncTtlVisibility);
    });
    reasonPresetEl?.addEventListener('change', syncReasonCustomVisibility);
    syncTtlVisibility();
    syncReasonCustomVisibility();

    bindSubmitHandler(async () => {
      const target = String(document.getElementById('ip-block-target-value')?.value || '').trim();
      const reasonPreset = String(document.getElementById('ip-block-reason-preset')?.value || '').trim();
      const reasonCustom = String(document.getElementById('ip-block-reason-custom')?.value || '').trim();
      const reason = reasonPreset === CUSTOM_REASON_VALUE ? reasonCustom : reasonPreset;
      const severityLevel = Number.parseInt(
        String(document.getElementById('ip-block-severity-level')?.value || '3'),
        10
      );
      const isPermanent = Boolean(document.getElementById('ip-block-mode-permanent')?.checked);
      const ttlValue = Number.parseInt(String(document.getElementById('ip-block-ttl-seconds')?.value || ''), 10);
      if (target === '') {
        throw new Error(i18n.targetRequired || 'Target is required.');
      }
      const targetValidation = validateTargetFormat(target);
      if (!targetValidation.ok) {
        if (targetValidation.code === 'cidr') {
          throw new Error(i18n.targetInvalidCidr || 'Target CIDR format is invalid.');
        }
        if (targetValidation.code === 'ip') {
          throw new Error(i18n.targetInvalidIp || 'Target IP format is invalid.');
        }
        throw new Error(i18n.targetRequired || 'Target is required.');
      }
      if (reason === '') {
        throw new Error(i18n.reasonRequired || 'Reason is required.');
      }
      if (!Number.isFinite(severityLevel) || severityLevel < 1 || severityLevel > 4) {
        throw new Error(i18n.severityInvalid || 'Severity is invalid.');
      }
      if (!isPermanent && (!Number.isFinite(ttlValue) || ttlValue < 1)) {
        throw new Error(i18n.ttlRequired || 'TTL must be greater than 0 for temporary block.');
      }

      const response = await fetch(api.upsert, {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          target,
          severity_level: severityLevel,
          reason,
          is_permanent: isPermanent,
          ttl_seconds: isPermanent ? null : ttlValue,
        }),
      });
      const payload = await parseJsonSafe(response);
      if (!response.ok) {
        const detail = typeof payload.detail === 'string' ? payload.detail : i18n.operationFailed;
        throw new Error(detail);
      }
      showSuccess(i18n.blockApplied || 'Block applied.');
    });
    modal.show();
  };

  const openReleaseBlockModal = (rowData) => {
    const releaseBase = String(api.releaseBase || '').trim();
    if (releaseBase === '') {
      showError(i18n.operationFailed || 'Operation failed');
      return;
    }
    const blockId = Number.parseInt(String(rowData?.id || ''), 10);
    if (!Number.isFinite(blockId) || blockId <= 0) {
      showError(i18n.operationFailed || 'Operation failed');
      return;
    }

    const bodyHtml = `
      <div class="mb-3">
        <div class="small mb-1"><span class="text-muted">IP:</span> <span id="ip-block-release-ip">-</span></div>
        <div class="small mb-1"><span class="text-muted">Severity:</span> <span id="ip-block-release-severity">-</span></div>
        <div class="small"><span class="text-muted">${escapeHtml(
          i18n.blockedReasonLabel || 'Blocked Reason'
        )}:</span> <span id="ip-block-release-reason">-</span></div>
      </div>
      <div class="mb-2">
        <label class="form-label" for="ip-block-release-reason-preset">${requiredLabel(
          i18n.releaseReasonLabel || 'Release Reason'
        )}</label>
        <select class="form-select" id="ip-block-release-reason-preset">
          ${createReasonPresetOptions({
            presets: releaseReasonPresets,
            placeholder: i18n.releaseReasonPresetPlaceholder || 'Select a release reason',
            customOption: i18n.releaseReasonCustomOption || 'Custom',
          })}
        </select>
      </div>
      <div class="mb-2 d-none" id="ip-block-release-custom-group">
        <label class="form-label" for="ip-block-release-reason-custom">${requiredLabel(
          i18n.releaseReasonCustomLabel || 'Custom Release Reason'
        )}</label>
        <input class="form-control" id="ip-block-release-reason-custom" maxlength="128" placeholder="${escapeHtml(
          i18n.releaseReasonCustomPlaceholder || ''
        )}" />
      </div>
    `;
    confirmModal.open({
      title: i18n.releaseAction || 'Release',
      bodyHtml,
      confirmText: i18n.confirm || 'Confirm',
      confirmClass: 'btn-primary',
      onConfirm: async () => {
        const selected = String(presetEl instanceof HTMLSelectElement ? presetEl.value : '').trim();
        const customReason = String(customEl instanceof HTMLInputElement ? customEl.value : '').trim();
        const releaseReason = selected === CUSTOM_REASON_VALUE ? customReason : selected;
        if (releaseReason === '') {
          throw new Error(i18n.releaseReasonRequired || 'Release reason is required.');
        }
        const response = await fetch(`${releaseBase}/${blockId}/release`, {
          method: 'POST',
          credentials: 'same-origin',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            release_reason: releaseReason,
          }),
        });
        const payload = await parseJsonSafe(response);
        if (!response.ok) {
          const detail = payload && typeof payload.detail === 'string' ? payload.detail : i18n.operationFailed;
          throw new Error(detail);
        }
        showSuccess(i18n.blockReleased || 'Block released.');
      },
    });
    const ipEl = document.getElementById('ip-block-release-ip');
    const severityEl = document.getElementById('ip-block-release-severity');
    const blockedReasonEl = document.getElementById('ip-block-release-reason');
    if (ipEl instanceof HTMLElement) {
      const target = String(rowData?.target_display || rowData?.target_network || '').trim();
      ipEl.textContent = target === '' ? '-' : target;
    }
    if (severityEl instanceof HTMLElement) {
      severityEl.textContent = getSeverityText(rowData?.severity_level);
    }
    if (blockedReasonEl instanceof HTMLElement) {
      blockedReasonEl.textContent = getBlockedReasonText(rowData);
    }

    const presetEl = document.getElementById('ip-block-release-reason-preset');
    const customGroupEl = document.getElementById('ip-block-release-custom-group');
    const customEl = document.getElementById('ip-block-release-reason-custom');
    const syncCustomInput = () => {
      const selected = String(presetEl instanceof HTMLSelectElement ? presetEl.value : '').trim();
      const isCustom = selected === CUSTOM_REASON_VALUE;
      if (customGroupEl instanceof HTMLElement) {
        customGroupEl.classList.toggle('d-none', !isCustom);
      }
      if (customEl instanceof HTMLInputElement) {
        customEl.disabled = !isCustom;
      }
    };
    if (presetEl instanceof HTMLSelectElement) {
      presetEl.addEventListener('change', syncCustomInput);
    }
    syncCustomInput();
  };

  injectAddBlockButton(openAddBlockModal);
  mountRowAction({
    tableSelector: '#dt',
    actionClassName: 'js-release-row-action',
    isVisible: isRowReleasable,
    buildButton: (viewAction) => {
      const button = document.createElement('a');
      button.href = '#';
      button.className = `${viewAction.className} ms-1`.trim();
      button.setAttribute('title', i18n.releaseAction || 'Release');
      button.innerHTML = '<i class="fa fa-key"></i>';
      return button;
    },
    onClick: (rowData, event) => {
      event.preventDefault();
      event.stopPropagation();
      openReleaseBlockModal(rowData);
    },
  });
};

void initPage();
