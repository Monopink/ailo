import { buildListQuery, fetchIncompleteList, fetchIncompleteOverview, ignoreIncompleteRequest } from './api.js';
import { withUtcTitle, safeText, showToast, escapeHtml, formatRelativeToNow } from './formatters.js';
import { refreshFilterOptions, renderUserIdCell } from './render-list.js';
import { AutoRetryModalController, ManualRetryModalController } from './retry-modal.js';
import { createPageState, STATUS_LABELS, CONTACT_TYPE_USER } from './state.js';

const config = window.ailoIncompleteContactRequestsPageConfig || {};
const API_BASE = config.apiBase || '/admin-api/contact-requests';
const ADMIN_BASE = config.adminBase || '/qiao-dash';
const TEMPLATE_LIST_PATH = config.templateListPath || '/qiao-dash/ai_template/list';
const CONTACT_REQUEST_DETAIL_PATH = config.contactRequestDetailPath || '/qiao-dash/contact_request/detail';

const state = createPageState();
const rowsById = new Map();
let dataTable = null;

const tableBody = document.getElementById('incomplete-table-body');
const autoRetryModalEl = document.getElementById('auto-retry-modal');
const manualRetryModalEl = document.getElementById('manual-retry-modal');
const ignoreRequestModalEl = document.getElementById('ignore-request-modal');
const totalHint = document.getElementById('list-total-hint');
const filterAiType = document.getElementById('filter-ai-type');
const filterFailureCode = document.getElementById('filter-failure-code');
const filterStatus = document.getElementById('filter-status');
const filterUpdatedFrom = document.getElementById('filter-updated-from');
const filterUpdatedTo = document.getElementById('filter-updated-to');
const autoRetryModal = window.bootstrap && autoRetryModalEl ? new window.bootstrap.Modal(autoRetryModalEl) : null;
const manualRetryModal = window.bootstrap && manualRetryModalEl ? new window.bootstrap.Modal(manualRetryModalEl) : null;
const ignoreRequestModal =
  window.bootstrap && ignoreRequestModalEl ? new window.bootstrap.Modal(ignoreRequestModalEl) : null;

const autoRetryElements = {
  requestId: document.getElementById('auto-retry-request-id'),
  requestAiType: document.getElementById('auto-retry-request-ai-type'),
  activeTemplateCount: document.getElementById('auto-retry-active-template-count'),
  selectableTemplateCount: document.getElementById('auto-retry-selectable-template-count'),
  expectedResult: document.getElementById('auto-retry-expected-result'),
  execSection: document.getElementById('auto-retry-exec-section'),
  execResult: document.getElementById('auto-retry-exec-result'),
  executeBtn: document.getElementById('btn-auto-retry-execute'),
};

const manualRetryElements = {
  stepMain: document.getElementById('manual-retry-step-main'),
  stepConfirm: document.getElementById('manual-retry-step-confirm'),
  requestId: document.getElementById('manual-retry-request-id'),
  requestAiType: document.getElementById('manual-retry-request-ai-type'),
  activeTemplateCount: document.getElementById('manual-retry-active-template-count'),
  selectableTemplateCount: document.getElementById('manual-retry-selectable-template-count'),
  aiTypeSelect: document.getElementById('manual-retry-ai-type-select'),
  aiTypeMismatchWarning: document.getElementById('manual-retry-ai-type-mismatch-warning'),
  templateSelect: document.getElementById('manual-retry-template-select'),
  templateDetail: document.getElementById('manual-retry-template-detail'),
  expectedResult: document.getElementById('manual-retry-expected-result'),
  confirmRequestId: document.getElementById('manual-retry-confirm-request-id'),
  confirmRequestAiType: document.getElementById('manual-retry-confirm-request-ai-type'),
  confirmTemplate: document.getElementById('manual-retry-confirm-template'),
  confirmRisk: document.getElementById('manual-retry-confirm-risk'),
  execSection: document.getElementById('manual-retry-exec-section'),
  execResult: document.getElementById('manual-retry-exec-result'),
  backBtn: document.getElementById('btn-manual-retry-back'),
  cancelBtn: document.getElementById('btn-manual-retry-cancel'),
  nextBtn: document.getElementById('btn-manual-retry-next'),
  confirmBtn: document.getElementById('btn-manual-retry-confirm'),
};

const ignoreState = {
  requestId: null,
  isSubmitting: false,
};

function findRowByRequestId(requestId) {
  return rowsById.get(safeText(requestId, '')) || null;
}

function goToUser(userId) {
  if (!userId) {
    showToast('缺少用户 ID，无法跳转用户页', true);
    return;
  }
  window.open(`${ADMIN_BASE}/user/detail/${encodeURIComponent(userId)}`, '_blank', 'noopener');
}

function goToTemplateList(aiTypeId) {
  const normalizedTypeId = safeText(aiTypeId, '').trim();
  if (!normalizedTypeId) {
    showToast('缺少 AI 类型，无法跳转模板页', true);
    return;
  }
  const query = new URLSearchParams({ search: normalizedTypeId });
  window.open(`${TEMPLATE_LIST_PATH}?${query.toString()}`, '_blank', 'noopener');
}

function goToContactRequestDetail(requestId) {
  const normalizedRequestId = safeText(requestId, '').trim();
  if (!normalizedRequestId) {
    showToast('缺少请求 ID，无法跳转详情页', true);
    return;
  }
  window.location.assign(`${CONTACT_REQUEST_DETAIL_PATH}/${encodeURIComponent(normalizedRequestId)}`);
}

function parseLocationState() {
  const params = new URLSearchParams(window.location.search);
  const rawPage = Number(params.get('page'));
  if (Number.isFinite(rawPage) && rawPage > 0) {
    state.page = Math.floor(rawPage);
  }
  const rawPageSize = Number(params.get('page_size'));
  if (Number.isFinite(rawPageSize) && rawPageSize > 0) {
    state.pageSize = Math.floor(rawPageSize);
  }
  if (filterAiType && params.get('ai_type_id')) {
    filterAiType.value = safeText(params.get('ai_type_id'), '');
  }
  if (filterFailureCode && params.get('failure_code')) {
    filterFailureCode.value = safeText(params.get('failure_code'), '');
  }
  if (filterStatus && params.get('status')) {
    filterStatus.value = safeText(params.get('status'), '');
  }
  if (filterUpdatedFrom && params.get('updated_from')) {
    const date = new Date(safeText(params.get('updated_from'), ''));
    if (!Number.isNaN(date.getTime())) {
      filterUpdatedFrom.value = date.toISOString().slice(0, 16);
    }
  }
  if (filterUpdatedTo && params.get('updated_to')) {
    const date = new Date(safeText(params.get('updated_to'), ''));
    if (!Number.isNaN(date.getTime())) {
      filterUpdatedTo.value = date.toISOString().slice(0, 16);
    }
  }
}

function updateUrlFromCurrentState() {
  if (!dataTable) return;
  const info = dataTable.page.info();
  const params = new URLSearchParams();
  if (filterAiType?.value) params.set('ai_type_id', filterAiType.value.trim());
  if (filterFailureCode?.value) params.set('failure_code', filterFailureCode.value.trim());
  if (filterStatus?.value) params.set('status', filterStatus.value.trim());
  if (filterUpdatedFrom?.value) params.set('updated_from', new Date(filterUpdatedFrom.value).toISOString());
  if (filterUpdatedTo?.value) params.set('updated_to', new Date(filterUpdatedTo.value).toISOString());
  params.set('page', String(info.page + 1));
  params.set('page_size', String(info.length));
  window.history.replaceState(null, '', `${window.location.pathname}?${params.toString()}`);
}

async function loadOverview() {
  const overview = await fetchIncompleteOverview(API_BASE);
  document.getElementById('metric-incomplete-total').textContent = safeText(overview.incomplete_total, '0');
  document.getElementById('metric-last24h-success').textContent = safeText(overview.last24h_success_requests, '0');
  document.getElementById('metric-last24h-failed').textContent = safeText(overview.last24h_failed_requests, '0');
  document.getElementById('metric-last24h-failed-attempts').textContent = safeText(
    overview.last24h_failed_attempts,
    '0'
  );
  document.getElementById('metric-last24h-blocked-attempts').textContent = safeText(
    overview.last24h_blocked_attempts,
    '0'
  );

  refreshFilterOptions(state, filterAiType, filterFailureCode);
}

function renderActionCell(row) {
  const requestId = escapeHtml(safeText(row.request_id));
  const retryDisabled = row.is_retryable ? '' : 'disabled';
  const supplementDisabled = row.ai_type_id ? '' : 'disabled';
  const ignoreDisabled = row.status === 8 ? 'disabled' : '';
  return `<div class="incomplete-action-group">
    <button class="btn btn-sm incomplete-action-btn action-view" data-request-id="${requestId}" title="查看详情"><i class="fa fa-eye"></i></button>
    <button class="btn btn-sm incomplete-action-btn action-supplement-template" data-ai-type-id="${escapeHtml(
      safeText(row.ai_type_id, '')
    )}" ${supplementDisabled} title="补模板"><i class="fa fa-external-link"></i></button>
    <button class="btn btn-sm incomplete-action-btn action-retry" data-request-id="${requestId}" ${retryDisabled} title="重试"><i class="fa fa-rotate-right"></i></button>
    <button class="btn btn-sm incomplete-action-btn action-template-retry" data-request-id="${requestId}" ${retryDisabled} title="指定模板重试"><i class="fa fa-random"></i></button>
    <button class="btn btn-sm incomplete-action-btn action-ignore" data-request-id="${requestId}" ${ignoreDisabled} title="忽略"><i class="fa fa-times-circle"></i></button>
  </div>`;
}

function setIgnoreModalState() {
  const idEl = document.getElementById('ignore-request-id');
  if (idEl) idEl.textContent = safeText(ignoreState.requestId);
  const confirmBtn = document.getElementById('btn-ignore-request-confirm');
  if (confirmBtn) {
    confirmBtn.disabled = ignoreState.isSubmitting || !ignoreState.requestId;
    confirmBtn.textContent = ignoreState.isSubmitting ? '处理中...' : '确认忽略';
  }
}

function openIgnoreModal(requestId) {
  ignoreState.requestId = requestId;
  ignoreState.isSubmitting = false;
  setIgnoreModalState();
  ignoreRequestModal?.show();
}

async function confirmIgnoreRequest() {
  if (!ignoreState.requestId || ignoreState.isSubmitting) return;
  ignoreState.isSubmitting = true;
  setIgnoreModalState();
  try {
    await ignoreIncompleteRequest(API_BASE, ignoreState.requestId);
    ignoreRequestModal?.hide();
    ignoreState.requestId = null;
    showToast('请求已忽略');
    await Promise.all([loadOverview(), reloadList()]);
  } catch (error) {
    showToast(error?.message || '忽略失败', true);
  } finally {
    ignoreState.isSubmitting = false;
    setIgnoreModalState();
  }
}

function renderValidityIcon(isExpired) {
  if (isExpired) {
    return '<span class="text-center text-danger" title="无效"><i class="fa-solid fa-times-circle fa-lg"></i></span>';
  }
  return '<span class="text-center text-success" title="有效"><i class="fa-solid fa-check-circle fa-lg"></i></span>';
}

function currentListQuery({ start, length }) {
  const page = Math.floor(start / Math.max(length, 1)) + 1;
  return buildListQuery({
    aiTypeId: filterAiType?.value,
    failureCode: filterFailureCode?.value,
    status: filterStatus?.value,
    page,
    pageSize: length,
    updatedFrom: filterUpdatedFrom?.value,
    updatedTo: filterUpdatedTo?.value,
  });
}

function initDataTable() {
  if (!window.jQuery || !window.jQuery.fn || !window.jQuery.fn.DataTable) {
    throw new Error('DataTables 未加载');
  }

  const $ = window.jQuery;
  dataTable = $('#incomplete-table').DataTable({
    dom: "r<'table-responsive't><'card-footer d-flex align-items-center'<'m-0'i><'m-0 ms-auto'p>>",
    paging: true,
    lengthChange: true,
    searching: false,
    info: true,
    ordering: false,
    processing: true,
    serverSide: true,
    pageLength: state.pageSize,
    displayStart: (Math.max(state.page, 1) - 1) * state.pageSize,
    lengthMenu: [20, 50, 100],
    pagingType: 'full_numbers',
    ajax: async function (data, callback) {
      try {
        const payload = await fetchIncompleteList(
          API_BASE,
          currentListQuery({ start: data.start, length: data.length })
        );
        const rows = Array.isArray(payload.items) ? payload.items : [];

        rowsById.clear();
        rows.forEach((row) => {
          const requestId = safeText(row.request_id, '');
          if (requestId) {
            rowsById.set(requestId, row);
          }
          if (row.ai_type_id) {
            state.aiTypeOptions.set(String(row.ai_type_id), String(row.ai_type_display_name || '未知类型'));
          }
          if (row.failure_code) {
            state.failureOptions.set(String(row.failure_code), String(row.failure_reason_label || '未知原因'));
          }
        });

        state.rows = rows;
        state.total = Number.isFinite(payload.total) ? Number(payload.total) : 0;
        totalHint.textContent = `共 ${safeText(state.total, '0')} 条`;
        refreshFilterOptions(state, filterAiType, filterFailureCode);

        callback({
          draw: data.draw,
          recordsTotal: state.total,
          recordsFiltered: state.total,
          data: rows,
        });

        updateUrlFromCurrentState();
      } catch (error) {
        callback({
          draw: data.draw,
          recordsTotal: 0,
          recordsFiltered: 0,
          data: [],
        });
        showToast(error?.message || '列表加载失败', true);
      }
    },
    columns: [
      {
        data: null,
        className: 'text-nowrap',
        render: (_, __, row) => renderActionCell(row),
      },
      {
        data: 'status',
        className: 'text-nowrap',
        render: (value) => escapeHtml(safeText(STATUS_LABELS[value], safeText(value))),
      },
      {
        data: 'created_at',
        className: 'text-nowrap',
        render: (value) =>
          `<span title="申请时间 UTC: ${escapeHtml(safeText(value))}">${escapeHtml(formatRelativeToNow(value))}</span>`,
      },
      {
        data: 'expires_at',
        className: 'text-nowrap',
        render: (value) =>
          `<span title="到期时间 UTC: ${escapeHtml(safeText(value))}">${escapeHtml(formatRelativeToNow(value))}</span>`,
      },
      {
        data: 'is_expired',
        className: 'text-nowrap text-center',
        render: (value) => renderValidityIcon(Boolean(value)),
      },
      {
        data: null,
        render: (_, __, row) =>
          `<div>From: ${escapeHtml(safeText(row.from_qiao_id))}</div><div>To: ${escapeHtml(
            safeText(row.to_qiao_id)
          )}</div>`,
      },
      {
        data: null,
        render: (_, __, row) => {
          const fromIdHtml = renderUserIdCell(row.from_id, row.from_type === CONTACT_TYPE_USER);
          const toIdHtml = renderUserIdCell(row.to_id, row.to_type === CONTACT_TYPE_USER);
          return `<div>FromID: ${fromIdHtml}</div><div>ToID: ${toIdHtml}</div>`;
        },
      },
      { data: 'failure_reason_label', render: (value) => escapeHtml(safeText(value)) },
      { data: 'ai_type_display_name', render: (value) => escapeHtml(safeText(value)) },
      { data: 'retry_count', className: 'text-nowrap', render: (value) => escapeHtml(safeText(value, '0')) },
      { data: 'last_retry_at', className: 'text-nowrap', render: (value) => withUtcTitle(value) },
      { data: 'updated_at', className: 'text-nowrap', render: (value) => withUtcTitle(value) },
    ],
  });
}

function reloadList({ resetPage = false } = {}) {
  if (!dataTable) return Promise.resolve();
  return new Promise((resolve) => {
    dataTable.one('draw', () => resolve());
    if (resetPage) {
      dataTable.page('first').draw('page');
      return;
    }
    dataTable.ajax.reload(null, false);
  });
}

function bindMainEvents(autoRetryController, manualRetryController) {
  document.getElementById('btn-filter-apply')?.addEventListener('click', () => {
    reloadList({ resetPage: true });
  });

  document.getElementById('btn-filter-reset')?.addEventListener('click', () => {
    if (filterAiType) filterAiType.value = '';
    if (filterFailureCode) filterFailureCode.value = '';
    if (filterStatus) filterStatus.value = '';
    if (filterUpdatedFrom) filterUpdatedFrom.value = '';
    if (filterUpdatedTo) filterUpdatedTo.value = '';
    reloadList({ resetPage: true });
  });

  tableBody.addEventListener('click', (event) => {
    const target = event.target.closest('button');
    if (!target) return;

    const requestId = target.dataset.requestId;
    const userId = target.dataset.userId;
    const aiTypeId = target.dataset.aiTypeId;

    if (target.classList.contains('action-open-user') && userId) {
      goToUser(userId);
      return;
    }
    if (target.classList.contains('action-supplement-template')) {
      goToTemplateList(aiTypeId);
      return;
    }
    if (target.classList.contains('action-view') && requestId) {
      goToContactRequestDetail(requestId);
      return;
    }
    if (target.classList.contains('action-retry') && requestId) {
      autoRetryController.open({ requestId });
      return;
    }
    if (target.classList.contains('action-template-retry') && requestId) {
      manualRetryController.open({ requestId });
      return;
    }
    if (target.classList.contains('action-ignore') && requestId) {
      openIgnoreModal(requestId);
    }
  });

  document.getElementById('btn-ignore-request-confirm')?.addEventListener('click', () => {
    confirmIgnoreRequest().catch(() => {});
  });
}

async function bootstrap() {
  if (!tableBody) return;

  parseLocationState();
  await loadOverview();
  initDataTable();

  const autoRetryController = new AutoRetryModalController({
    apiBase: API_BASE,
    modal: autoRetryModal,
    elements: autoRetryElements,
    findRowByRequestId,
    onAfterExecute: async () => {
      await Promise.all([loadOverview(), reloadList()]);
    },
  });

  const manualRetryController = new ManualRetryModalController({
    apiBase: API_BASE,
    modal: manualRetryModal,
    modalEl: manualRetryModalEl,
    elements: manualRetryElements,
    findRowByRequestId,
    onAfterExecute: async () => {
      await Promise.all([loadOverview(), reloadList()]);
    },
  });

  bindMainEvents(autoRetryController, manualRetryController);
  autoRetryController.bindEvents();
  manualRetryController.bindEvents();
}

document.addEventListener('DOMContentLoaded', () => {
  bootstrap().catch((error) => {
    if (tableBody) {
      tableBody.innerHTML = '<tr><td colspan="12" class="text-center text-danger">加载失败</td></tr>';
    }
    showToast(error?.message || '初始化失败', true);
  });
});
