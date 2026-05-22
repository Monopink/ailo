import { executeRetryRequest, fetchRetryPrecheck } from './api.js';
import { buildRetryIdempotencyKey, escapeHtml, formatDateTime, safeText, showToast } from './formatters.js';

function getWarnings(precheck) {
  return Array.isArray(precheck?.warnings) ? precheck.warnings : [];
}

function getBlockingErrors(precheck) {
  return Array.isArray(precheck?.blocking_errors) ? precheck.blocking_errors : [];
}

function formatAiTypeText(aiTypeId, aiTypeName) {
  const idText = safeText(aiTypeId, '');
  const nameText = safeText(aiTypeName, '');
  if (!idText && !nameText) return '-';
  if (!idText) return nameText;
  if (!nameText) return idText;
  return `${idText} · ${nameText}`;
}

function formatExpectedResult({ hasRisk, hasBlocking, precheckError, warnings, blockingErrors }) {
  if (precheckError) return `预检失败（视为存在风险）：${precheckError}`;
  if (hasBlocking) {
    const blockingMessages = blockingErrors.map((item) => safeText(item.message)).join('；');
    return blockingMessages ? `不可执行：${blockingMessages}` : '不可执行：命中阻断规则';
  }
  if (!hasRisk) return '预计可重试成功';
  const warningMessages = warnings.map((item) => safeText(item.message)).join('；');
  return warningMessages ? `存在风险：${warningMessages}` : '存在风险，请谨慎继续';
}

function buildExecutionResultText(payload) {
  const status = safeText(payload?.result_status, 'UNKNOWN');
  const resultFailureCode = safeText(payload?.result_failure_code, '');
  const failureCodeSuffix = resultFailureCode ? '，失败码：' + resultFailureCode : '';
  const replayText = payload?.is_idempotent_replay ? '（幂等回放）' : '';

  if (status === 'SUCCESS') {
    return {
      text: '执行成功' + replayText + '：重试成功',
      isSuccess: true,
      isError: false,
      shouldDisable: true,
    };
  }

  if (status === 'FAILED') {
    return {
      text: '执行完成' + replayText + '：重试失败' + failureCodeSuffix,
      isSuccess: false,
      isError: true,
      shouldDisable: false,
    };
  }

  if (status === 'REJECTED') {
    if (resultFailureCode === 'AI_CONTACT_LIMIT_REACHED') {
      const availableTotal = payload?.result_failure_detail?.available_total;
      const quotaText = Number.isFinite(availableTotal) ? '（剩余额度：' + availableTotal + '）' : '';
      return {
        text: '重试成功' + replayText + '：但是由于联系人数量达到上限，联系人没有添加' + quotaText,
        isSuccess: true,
        isError: false,
        shouldDisable: true,
      };
    }
    return {
      text: '执行完成' + replayText + '：重试被拒绝' + failureCodeSuffix,
      isSuccess: false,
      isError: true,
      shouldDisable: false,
    };
  }

  return {
    text: '执行异常' + replayText + failureCodeSuffix,
    isSuccess: false,
    isError: true,
    shouldDisable: false,
  };
}

class RetryExecutionBase {
  constructor(options) {
    this.apiBase = options.apiBase;
    this.onAfterExecute = options.onAfterExecute;
  }

  buildFallbackPrecheckPayload(errorMessage) {
    return {
      checks: [],
      blocking_errors: [],
      warnings: [{ code: 'PRECHECK_FAILED', level: 'HIGH', message: safeText(errorMessage, '预检失败') }],
      summary: { blocking_count: 0, warning_count: 1, high_risk_count: 1, can_execute: false },
      availability: { active_template_count: 0, selectable_template_count: 0 },
    };
  }
}

export class AutoRetryModalController extends RetryExecutionBase {
  constructor(options) {
    super(options);
    this.modal = options.modal;
    this.elements = options.elements;
    this.findRowByRequestId = options.findRowByRequestId;
    this.state = {
      requestId: null,
      precheck: null,
      precheckError: null,
      hasBlocking: false,
      hasRisk: false,
    };
    this.precheckRequestSeq = 0;
  }

  setExpectedResultText(text, hasRisk) {
    this.elements.expectedResult.textContent = text;
    this.elements.expectedResult.classList.toggle('retry-result-risk', hasRisk);
  }

  setExecutionResultText(text, { isError = false, isSuccess = false } = {}) {
    this.elements.execResult.textContent = text;
    this.elements.execResult.classList.toggle('retry-result-risk', isError);
    this.elements.execResult.classList.toggle('retry-result-success', isSuccess);
  }

  resetState() {
    this.state.precheck = null;
    this.state.precheckError = null;
    this.state.hasBlocking = false;
    this.state.hasRisk = false;
    this.elements.requestId.textContent = '-';
    this.elements.requestAiType.textContent = '-';
    this.elements.activeTemplateCount.textContent = '-';
    this.elements.selectableTemplateCount.textContent = '-';
    this.elements.executeBtn.disabled = true;
    this.elements.executeBtn.textContent = '重试';
    this.setExpectedResultText('预检中...', false);
    this.setExecutionResultText('尚未执行');
  }

  applyPrecheckSnapshot(precheck) {
    const availability = precheck?.availability || {};
    const warnings = getWarnings(precheck);
    const blockingErrors = getBlockingErrors(precheck);
    this.state.precheck = precheck;
    this.state.precheckError = null;
    this.state.hasBlocking = blockingErrors.length > 0;
    this.state.hasRisk = warnings.length > 0;

    this.elements.requestAiType.textContent = formatAiTypeText(
      precheck?.requested_ai_type_id,
      precheck?.requested_ai_type_name
    );
    this.elements.activeTemplateCount.textContent = safeText(availability.active_template_count, '0');
    this.elements.selectableTemplateCount.textContent = safeText(availability.selectable_template_count, '0');
    this.setExpectedResultText(
      formatExpectedResult({
        hasRisk: this.state.hasRisk,
        hasBlocking: this.state.hasBlocking,
        precheckError: null,
        warnings,
        blockingErrors,
      }),
      this.state.hasRisk || this.state.hasBlocking
    );
    this.elements.executeBtn.textContent = this.state.hasBlocking
      ? '不可执行'
      : this.state.hasRisk
        ? '强制重试'
        : '重试';
    this.elements.executeBtn.disabled = this.state.hasBlocking;
  }

  applyPrecheckFailure(errorMessage) {
    this.state.precheck = null;
    this.state.precheckError = safeText(errorMessage, '预检失败');
    this.state.hasBlocking = false;
    this.state.hasRisk = true;
    this.setExpectedResultText(
      formatExpectedResult({
        hasRisk: true,
        hasBlocking: false,
        precheckError: this.state.precheckError,
        warnings: [],
        blockingErrors: [],
      }),
      true
    );
    this.elements.executeBtn.textContent = '强制重试';
    this.elements.executeBtn.disabled = false;
  }

  async runPrecheck() {
    if (!this.state.requestId) return;
    this.setExpectedResultText('预检中...', false);
    const requestSeq = ++this.precheckRequestSeq;
    try {
      const precheck = await fetchRetryPrecheck(this.apiBase, this.state.requestId, { mode: 'AUTO' });
      if (requestSeq !== this.precheckRequestSeq) return;
      this.applyPrecheckSnapshot(precheck);
    } catch (error) {
      if (requestSeq !== this.precheckRequestSeq) return;
      this.applyPrecheckFailure(error?.message || '预检失败');
    }
  }

  buildPrecheckPayloadForExecute() {
    if (this.state.precheck) return this.state.precheck;
    return this.buildFallbackPrecheckPayload(this.state.precheckError);
  }

  async executeRetry() {
    if (!this.state.requestId) {
      this.setExecutionResultText('执行失败：缺少请求ID', { isError: true });
      return;
    }
    const body = {
      mode: 'AUTO',
      selected_ai_type_id: null,
      selected_template_id: null,
      force_continue: this.state.hasRisk && !this.state.hasBlocking,
      idempotency_key: buildRetryIdempotencyKey(this.state.requestId, 'AUTO'),
      precheck_payload: this.buildPrecheckPayloadForExecute(),
    };

    this.elements.executeBtn.disabled = true;
    this.setExecutionResultText('执行中...');
    try {
      const payload = await executeRetryRequest(this.apiBase, this.state.requestId, body);
      const executionResult = buildExecutionResultText(payload);
      this.setExecutionResultText(executionResult.text, {
        isSuccess: executionResult.isSuccess,
        isError: executionResult.isError,
      });
      if (!executionResult.shouldDisable) {
        this.elements.executeBtn.disabled = false;
      }
      try {
        await this.onAfterExecute(this.state.requestId);
      } catch (refreshError) {
        showToast(`执行已完成，但刷新失败：${safeText(refreshError?.message, '系统错误')}`, true);
      }
    } catch (error) {
      this.setExecutionResultText(`执行失败：${safeText(error?.message, '系统错误')}`, { isError: true });
      this.elements.executeBtn.disabled = false;
    }
  }

  open({ requestId }) {
    this.state.requestId = requestId;
    this.resetState();
    this.elements.requestId.textContent = safeText(requestId);
    const currentRow = this.findRowByRequestId(requestId);
    this.elements.requestAiType.textContent = formatAiTypeText(
      currentRow?.ai_type_id,
      currentRow?.ai_type_display_name
    );
    this.runPrecheck().catch(() => {});
    this.modal?.show();
  }

  bindEvents() {
    this.elements.executeBtn?.addEventListener('click', () => {
      if (this.state.hasBlocking) {
        this.setExecutionResultText('执行失败：命中阻断规则，不允许提交', { isError: true });
        return;
      }
      this.executeRetry().catch(() => {});
    });
  }
}

export class ManualRetryModalController extends RetryExecutionBase {
  constructor(options) {
    super(options);
    this.modal = options.modal;
    this.modalEl = options.modalEl;
    this.elements = options.elements;
    this.findRowByRequestId = options.findRowByRequestId;
    this.state = {
      requestId: null,
      requestAiTypeId: null,
      selectedAiTypeId: null,
      selectedAiTypeMeta: null,
      selectedTemplateId: null,
      selectedTemplateMeta: null,
      precheck: null,
      precheckError: null,
      hasBlocking: false,
      hasRisk: false,
      step: 'main',
    };
    this.precheckRequestSeq = 0;
  }

  setExpectedResultText(text, hasRisk) {
    this.elements.expectedResult.textContent = text;
    this.elements.expectedResult.classList.toggle('retry-result-risk', hasRisk);
  }

  setExecutionResultText(text, { isError = false, isSuccess = false } = {}) {
    this.elements.execResult.textContent = text;
    this.elements.execResult.classList.toggle('retry-result-risk', isError);
    this.elements.execResult.classList.toggle('retry-result-success', isSuccess);
  }

  updateNextButtonState() {
    this.elements.nextBtn.disabled =
      this.state.hasBlocking || (!this.state.selectedAiTypeId && !this.state.selectedTemplateId);
  }

  updateTemplateSelectState() {
    const canUseTemplateSearch = !!this.state.selectedAiTypeId;
    if (this.elements.templateSelect) {
      this.elements.templateSelect.disabled = !canUseTemplateSearch;
    }
  }

  updateAiTypeMismatchWarning() {
    if (!this.elements.aiTypeMismatchWarning) return;
    const shouldShow =
      !!this.state.requestAiTypeId &&
      !!this.state.selectedAiTypeId &&
      this.state.requestAiTypeId !== this.state.selectedAiTypeId;
    this.elements.aiTypeMismatchWarning.classList.toggle('d-none', !shouldShow);
  }

  renderTemplateDetail(meta) {
    if (!meta) {
      this.elements.templateDetail.classList.add('d-none');
      this.elements.templateDetail.innerHTML = '';
      return;
    }
    const reusableText = meta.is_reusable ? '可复用' : '单次';
    const styleText = safeText(meta.style_display_name, safeText(meta.style_id));
    const personalityText = safeText(meta.personality_display_name, safeText(meta.personality_id));
    this.elements.templateDetail.classList.remove('d-none');
    this.elements.templateDetail.innerHTML = `
      <div class="retry-template-detail-item"><strong>ID:</strong> ${escapeHtml(safeText(meta.template_id))}</div>
      <div class="retry-template-detail-item"><strong>名称:</strong> ${escapeHtml(safeText(meta.display_name))}</div>
      <div class="retry-template-detail-item"><strong>类型:</strong> ${escapeHtml(
        safeText(meta.type_id)
      )} · ${escapeHtml(safeText(meta.type_display_name))}</div>
      <div class="retry-template-detail-item"><strong>状态:</strong> ${escapeHtml(safeText(meta.status))}</div>
      <div class="retry-template-detail-item"><strong>复用:</strong> ${escapeHtml(reusableText)}</div>
      <div class="retry-template-detail-item"><strong>优先级:</strong> ${escapeHtml(safeText(meta.priority))}</div>
      <div class="retry-template-detail-item"><strong>Style:</strong> ${escapeHtml(styleText)}</div>
      <div class="retry-template-detail-item"><strong>Personality:</strong> ${escapeHtml(personalityText)}</div>
      <div class="retry-template-detail-item"><strong>Timezone:</strong> ${escapeHtml(safeText(meta.timezone))}</div>
      <div class="retry-template-detail-item"><strong>更新:</strong> ${escapeHtml(
        formatDateTime(meta.updated_at)
      )}</div>
    `;
  }

  resetState() {
    this.state.requestAiTypeId = null;
    this.state.selectedAiTypeId = null;
    this.state.selectedAiTypeMeta = null;
    this.state.selectedTemplateId = null;
    this.state.selectedTemplateMeta = null;
    this.state.precheck = null;
    this.state.precheckError = null;
    this.state.hasBlocking = false;
    this.state.hasRisk = false;
    this.state.step = 'main';

    this.elements.requestId.textContent = '-';
    this.elements.requestAiType.textContent = '-';
    this.elements.activeTemplateCount.textContent = '-';
    this.elements.selectableTemplateCount.textContent = '-';

    this.elements.stepMain.classList.remove('d-none');
    this.elements.stepConfirm.classList.add('d-none');
    this.elements.execSection.classList.add('d-none');

    this.elements.backBtn.classList.add('d-none');
    this.elements.confirmBtn.classList.add('d-none');
    this.elements.cancelBtn.classList.remove('d-none');
    this.elements.nextBtn.classList.remove('d-none');
    this.elements.nextBtn.disabled = true;

    this.setExpectedResultText('待预检', false);
    this.setExecutionResultText('尚未执行');
    this.renderTemplateDetail(null);
    this.updateTemplateSelectState();
    this.updateAiTypeMismatchWarning();
  }

  applyPrecheckSnapshot(precheck) {
    const availability = precheck?.availability || {};
    const warnings = getWarnings(precheck);
    const blockingErrors = getBlockingErrors(precheck);
    this.state.precheck = precheck;
    this.state.precheckError = null;
    this.state.hasBlocking = blockingErrors.length > 0;
    this.state.hasRisk = warnings.length > 0;
    this.elements.activeTemplateCount.textContent = safeText(availability.active_template_count, '0');
    this.elements.selectableTemplateCount.textContent = safeText(availability.selectable_template_count, '0');
    this.setExpectedResultText(
      formatExpectedResult({
        hasRisk: this.state.hasRisk,
        hasBlocking: this.state.hasBlocking,
        precheckError: null,
        warnings,
        blockingErrors,
      }),
      this.state.hasRisk || this.state.hasBlocking
    );
    this.updateNextButtonState();
  }

  applyPrecheckFailure(errorMessage) {
    this.state.precheck = null;
    this.state.precheckError = safeText(errorMessage, '预检失败');
    this.state.hasBlocking = false;
    this.state.hasRisk = true;
    this.setExpectedResultText(
      formatExpectedResult({
        hasRisk: true,
        hasBlocking: false,
        precheckError: this.state.precheckError,
        warnings: [],
        blockingErrors: [],
      }),
      true
    );
    this.updateNextButtonState();
  }

  async runPrecheck() {
    if (!this.state.requestId || (!this.state.selectedAiTypeId && !this.state.selectedTemplateId)) return;
    this.setExpectedResultText('预检中...', false);
    const requestSeq = ++this.precheckRequestSeq;
    const selectedAiTypeId = this.state.selectedAiTypeId;
    const selectedTemplateId = this.state.selectedTemplateId;
    const body = {
      mode: 'MANUAL',
      selected_ai_type_id: selectedAiTypeId,
      selected_template_id: selectedTemplateId,
    };
    try {
      const precheck = await fetchRetryPrecheck(this.apiBase, this.state.requestId, body);
      if (requestSeq !== this.precheckRequestSeq) return;
      if (selectedAiTypeId !== this.state.selectedAiTypeId) return;
      if (selectedTemplateId !== this.state.selectedTemplateId) return;
      const responseSelectedAiTypeId = precheck?.selected_ai_type_id ? String(precheck.selected_ai_type_id) : null;
      if (
        responseSelectedAiTypeId &&
        this.state.selectedAiTypeId &&
        responseSelectedAiTypeId !== this.state.selectedAiTypeId
      ) {
        return;
      }
      this.applyPrecheckSnapshot(precheck);
    } catch (error) {
      if (requestSeq !== this.precheckRequestSeq) return;
      this.applyPrecheckFailure(error?.message || '预检失败');
    }
  }

  buildPrecheckPayloadForExecute() {
    if (this.state.precheck) return this.state.precheck;
    return this.buildFallbackPrecheckPayload(this.state.precheckError);
  }

  async executeRetry() {
    if (!this.state.requestId) {
      this.setExecutionResultText('执行失败：缺少请求ID', { isError: true });
      return;
    }
    const body = {
      mode: 'MANUAL',
      selected_ai_type_id: this.state.selectedAiTypeId,
      selected_template_id: this.state.selectedTemplateId,
      force_continue: this.state.hasRisk && !this.state.hasBlocking,
      idempotency_key: buildRetryIdempotencyKey(this.state.requestId, 'MANUAL'),
      precheck_payload: this.buildPrecheckPayloadForExecute(),
    };

    this.elements.confirmBtn.disabled = true;
    this.setExecutionResultText('执行中...');
    try {
      const payload = await executeRetryRequest(this.apiBase, this.state.requestId, body);
      const executionResult = buildExecutionResultText(payload);
      this.setExecutionResultText(executionResult.text, {
        isSuccess: executionResult.isSuccess,
        isError: executionResult.isError,
      });
      if (!executionResult.shouldDisable) {
        this.elements.confirmBtn.disabled = false;
      }
      try {
        await this.onAfterExecute(this.state.requestId);
      } catch (refreshError) {
        showToast(`执行已完成，但刷新失败：${safeText(refreshError?.message, '系统错误')}`, true);
      }
    } catch (error) {
      this.setExecutionResultText(`执行失败：${safeText(error?.message, '系统错误')}`, { isError: true });
      this.elements.confirmBtn.disabled = false;
    }
  }

  openConfirmStep() {
    if (this.state.hasBlocking) {
      showToast('命中阻断规则，当前配置不可执行', true);
      return;
    }
    this.state.step = 'confirm';
    this.elements.stepMain.classList.add('d-none');
    this.elements.stepConfirm.classList.remove('d-none');
    this.elements.execSection.classList.remove('d-none');

    this.elements.backBtn.classList.remove('d-none');
    this.elements.confirmBtn.classList.remove('d-none');
    this.elements.cancelBtn.classList.add('d-none');
    this.elements.nextBtn.classList.add('d-none');

    this.elements.confirmRequestId.textContent = safeText(this.state.requestId);
    this.elements.confirmRequestAiType.textContent = this.elements.requestAiType.textContent;
    this.elements.confirmTemplate.textContent = this.state.selectedTemplateMeta
      ? `${safeText(this.state.selectedTemplateMeta.template_id)} · ${safeText(
          this.state.selectedTemplateMeta.display_name
        )}`
      : '系统自动选择（按所选 AI 类型）';
    this.elements.confirmRisk.textContent = this.elements.expectedResult.textContent;
    this.elements.confirmBtn.textContent = '确认';
    this.elements.confirmBtn.disabled = false;
  }

  backToMainStep() {
    this.state.step = 'main';
    this.elements.stepMain.classList.remove('d-none');
    this.elements.stepConfirm.classList.add('d-none');
    this.elements.execSection.classList.add('d-none');

    this.elements.backBtn.classList.add('d-none');
    this.elements.confirmBtn.classList.add('d-none');
    this.elements.cancelBtn.classList.remove('d-none');
    this.elements.nextBtn.classList.remove('d-none');
    this.elements.confirmBtn.textContent = '确认';
    this.updateNextButtonState();
  }

  applySelectedAiType(data) {
    const meta = data && typeof data.meta === 'object' ? data.meta : null;
    this.state.selectedAiTypeId = data?.id ? String(data.id) : null;
    this.state.selectedAiTypeMeta = meta;
    this.state.selectedTemplateId = null;
    this.state.selectedTemplateMeta = null;
    this.state.precheck = null;
    this.state.precheckError = null;
    this.state.hasBlocking = false;
    this.state.hasRisk = false;
    this.elements.activeTemplateCount.textContent = '-';
    this.elements.selectableTemplateCount.textContent = '-';
    this.renderTemplateDetail(null);

    this.updateTemplateSelectState();
    this.updateAiTypeMismatchWarning();
    if (window.jQuery && this.elements.templateSelect) {
      window.jQuery(this.elements.templateSelect).val(null).trigger('change');
      if (this.state.selectedAiTypeId) {
        window.setTimeout(() => {
          try {
            window.jQuery(this.elements.templateSelect).select2('open');
          } catch {}
        }, 0);
      }
    }

    if (!this.state.selectedAiTypeId) {
      if (!this.state.selectedTemplateId) {
        this.setExpectedResultText('待预检', false);
      }
      this.updateNextButtonState();
      return;
    }
    this.runPrecheck().catch((error) => {
      this.applyPrecheckFailure(error?.message || '预检失败');
    });
  }

  initAiTypeSearchSelect() {
    const searchSelect = window.ailoSearchSelect;
    if (!searchSelect || typeof searchSelect.initSearchSelect !== 'function' || !this.elements.aiTypeSelect) {
      this.setExecutionResultText('初始化失败：AI类型搜索组件未加载', { isError: true });
      return;
    }
    searchSelect.initSearchSelect({
      element: this.elements.aiTypeSelect,
      searchUrl: `${this.apiBase}/ai-types/search`,
      placeholder: '输入 AI 类型 ID 或名称搜索',
      minimumInputLength: 0,
      limit: 20,
      dropdownParent: this.modalEl,
      allowClear: true,
      language: {
        inputTooShort: '请输入至少 1 个字符',
        noResults: '未找到 AI 类型',
        searching: '搜索中...',
        errorLoading: 'AI 类型查询失败',
      },
      onSelect: (data) => {
        this.applySelectedAiType(data);
      },
      onClear: () => {
        this.applySelectedAiType(null);
      },
    });
  }

  initTemplateSearchSelect() {
    const searchSelect = window.ailoSearchSelect;
    if (!searchSelect || typeof searchSelect.initSearchSelect !== 'function' || !this.elements.templateSelect) {
      this.setExecutionResultText('初始化失败：模板搜索组件未加载', { isError: true });
      return;
    }
    searchSelect.initSearchSelect({
      element: this.elements.templateSelect,
      searchUrl: `${this.apiBase}/templates/search`,
      placeholder: '输入模板 ID 或名称搜索',
      minimumInputLength: 0,
      limit: 50,
      dropdownParent: this.modalEl,
      allowClear: true,
      buildQueryParams: () => ({ ai_type_id: this.state.selectedAiTypeId }),
      language: {
        inputTooShort: '请输入至少 1 个字符',
        noResults: '未找到模板',
        searching: '搜索中...',
        errorLoading: '模板查询失败',
      },
      onSelect: (data) => {
        const meta = data && typeof data.meta === 'object' ? data.meta : null;
        this.state.selectedTemplateId = data?.id ? String(data.id) : null;
        this.state.selectedTemplateMeta = meta;
        this.state.precheck = null;
        this.state.precheckError = null;
        this.state.hasBlocking = false;
        this.state.hasRisk = false;
        this.renderTemplateDetail(meta);
        this.runPrecheck().catch((error) => {
          this.applyPrecheckFailure(error?.message || '预检失败');
        });
      },
      onClear: () => {
        this.state.selectedTemplateId = null;
        this.state.selectedTemplateMeta = null;
        this.state.precheck = null;
        this.state.precheckError = null;
        this.state.hasBlocking = false;
        this.state.hasRisk = false;
        this.renderTemplateDetail(null);
        if (this.state.selectedAiTypeId) {
          this.runPrecheck().catch((error) => {
            this.applyPrecheckFailure(error?.message || '预检失败');
          });
        } else {
          this.setExpectedResultText('待预检', false);
          this.updateNextButtonState();
        }
      },
    });
  }

  open({ requestId }) {
    this.state.requestId = requestId;
    this.resetState();
    this.elements.requestId.textContent = safeText(requestId);
    const currentRow = this.findRowByRequestId(requestId);
    this.state.requestAiTypeId = currentRow?.ai_type_id ? String(currentRow.ai_type_id) : null;
    this.elements.requestAiType.textContent = formatAiTypeText(
      currentRow?.ai_type_id,
      currentRow?.ai_type_display_name
    );

    this.initAiTypeSearchSelect();
    this.initTemplateSearchSelect();

    const defaultAiTypeId = currentRow?.ai_type_id ? String(currentRow.ai_type_id) : null;
    const defaultAiTypeName = currentRow?.ai_type_display_name ? String(currentRow.ai_type_display_name) : '';
    if (defaultAiTypeId && window.jQuery && this.elements.aiTypeSelect) {
      const aiType = window.jQuery(this.elements.aiTypeSelect);
      if (aiType.find(`option[value="${defaultAiTypeId}"]`).length === 0) {
        aiType.append(
          new Option(`[${defaultAiTypeId}] ${defaultAiTypeName || defaultAiTypeId}`, defaultAiTypeId, false, false)
        );
      }
      aiType.val(defaultAiTypeId).trigger('change');
      this.applySelectedAiType({
        id: defaultAiTypeId,
        text: `[${defaultAiTypeId}] ${defaultAiTypeName || defaultAiTypeId}`,
        meta: {
          ai_type_id: defaultAiTypeId,
          ai_type_display_name: defaultAiTypeName || null,
        },
      });
    }

    this.modal?.show();
  }

  bindEvents() {
    this.elements.nextBtn?.addEventListener('click', () => {
      if (!this.state.selectedAiTypeId && !this.state.selectedTemplateId) {
        showToast('请至少选择 AI 类型或模板', true);
        return;
      }
      this.openConfirmStep();
    });

    this.elements.backBtn?.addEventListener('click', () => {
      this.backToMainStep();
    });

    this.elements.confirmBtn?.addEventListener('click', () => {
      if (this.state.hasBlocking) {
        this.setExecutionResultText('执行失败：命中阻断规则，不允许提交', { isError: true });
        return;
      }
      this.executeRetry().catch(() => {});
    });
  }
}
