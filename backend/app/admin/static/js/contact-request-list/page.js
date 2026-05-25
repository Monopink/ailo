import { mountRowAction } from '../components/list-row-action-injector.js';
import { createConfirmActionModal } from '../components/confirm-action-modal.js';
import { createPageFeedback } from '../components/page-feedback.js';

const config = window.ailoContactRequestListConfig || {};
const api = config.api || {};
const i18n = config.i18n || {};
const feedback = createPageFeedback({ containerId: 'contact-request-list-feedback' });

const isTruthy = (value) => value === true;

const parseJsonSafe = async (response) => {
  try {
    return await response.json();
  } catch {
    return {};
  }
};

const showError = (message) => {
  feedback.error(message || i18n.operationFailed || 'Operation failed');
};

const showSuccess = (message) => {
  feedback.success(message || '');
};

const isIgnoredStatus = (statusRaw) => {
  const expected = Number.parseInt(String(config.ignoredStatus || '3'), 10);
  const actual = Number.parseInt(String(statusRaw || ''), 10);
  if (Number.isFinite(expected) && Number.isFinite(actual)) {
    return actual === expected;
  }
  const normalized = String(statusRaw || '')
    .trim()
    .toLowerCase();
  return normalized === 'ignored';
};

const getRequestId = (rowData) => {
  const raw = rowData?.id;
  const parsed = Number.parseInt(String(raw || ''), 10);
  if (Number.isFinite(parsed) && parsed > 0) {
    return parsed;
  }
  return null;
};

const reopenPendingRequest = async (requestId) => {
  const reopenBase = String(api.reopenBase || '').trim();
  if (reopenBase === '') {
    throw new Error(i18n.operationFailed || 'Operation failed');
  }
  const response = await fetch(`${reopenBase}/${requestId}/reopen-pending`, {
    method: 'POST',
    credentials: 'same-origin',
  });
  const payload = await parseJsonSafe(response);
  if (!response.ok) {
    const detail = payload && typeof payload.detail === 'string' ? payload.detail : i18n.operationFailed;
    throw new Error(detail || 'Operation failed');
  }
};

const initPage = () => {
  if (!isTruthy(config.canOperate)) {
    return;
  }
  const confirmModal = createConfirmActionModal({
    modalId: 'contact-request-reopen-confirm-modal',
    cancelText: i18n.cancel || 'Cancel',
    defaultErrorMessage: i18n.operationFailed || 'Operation failed',
    showAlert: showError,
    reloadOnSuccess: true,
  });

  mountRowAction({
    tableSelector: '#dt',
    actionClassName: 'js-reopen-row-action',
    isVisible: (rowData) => isIgnoredStatus(rowData?.status),
    buildButton: (viewAction) => {
      const button = document.createElement('a');
      button.href = '#';
      button.className = `${viewAction.className} ms-1`.trim();
      button.setAttribute('title', i18n.reopenAction || '恢复待处理');
      button.innerHTML = '<i class="fa fa-rotate-left"></i>';
      return button;
    },
    onClick: async (rowData, event) => {
      event.preventDefault();
      event.stopPropagation();
      const requestId = getRequestId(rowData);
      if (requestId === null) {
        showError(i18n.operationFailed || 'Operation failed');
        return;
      }
      confirmModal.open({
        title: i18n.reopenAction || '恢复待处理',
        bodyHtml: `<div>${i18n.reopenConfirm || '是否将此请求修改为 Pending 状态，并重新在未完成消息面板可用？'}</div>`,
        confirmText: i18n.confirm || 'Confirm',
        confirmClass: 'btn-primary',
        onConfirm: async () => {
          await reopenPendingRequest(requestId);
          showSuccess(i18n.reopenSuccess || '请求已恢复为待处理');
        },
      });
    },
  });
};

void initPage();
