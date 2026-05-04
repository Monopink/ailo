const config = window.ailoAdvancedEditPersonalityConfig || {};

function requireNumericId(value, name) {
  const strValue = typeof value === 'string' ? value : String(value ?? '');
  if (!/^\d+$/.test(strValue)) {
    throw new Error(`Invalid ${name} for AI personality advanced edit page`);
  }
  return strValue;
}

const PERSONALITY_ID = requireNumericId(config.personalityId, 'personalityId');
const ADVANCED_CONFIG_URL = `/admin-api/ai/ai-personality/${PERSONALITY_ID}/advanced-config`;

export const personalityStyleMethods = {
  async loadAdvancedConfig() {
    const response = await fetch(ADVANCED_CONFIG_URL);
    if (!response.ok) {
      const errorPayload = await response.json().catch(() => ({}));
      throw new Error(errorPayload.detail || '加载高级配置失败');
    }
    const data = await response.json();
    const personality = data?.personality || {};
    const promptEditor = document.getElementById('prompt-editor');
    if (promptEditor && typeof personality.prompt === 'string') {
      promptEditor.value = personality.prompt;
    }

    this.state.fieldEntries = Array.isArray(data?.field_entries)
      ? data.field_entries.map((item) => ({
          key: item.key || item.name || '',
          name: item.name || '',
          display_name: item.display_name || '',
          group: item.group || 'custom',
          type: item.type || 'string',
          required: !!item.required,
          description: item.description || '',
          default_description: item.default_description || '',
          editable_description: item.editable_description !== false,
          restorable: item.restorable !== false,
          deletable: item.deletable === true,
          locked_name: item.locked_name !== false,
          locked_type: item.locked_type !== false,
          locked_required: item.locked_required !== false,
          min: Number.isFinite(Number(item.min)) ? Number(item.min) : null,
          max: Number.isFinite(Number(item.max)) ? Number(item.max) : null,
          is_default: !!item.is_default,
          exists: item.exists !== false,
        }))
      : [];
    this.state.orphanScoreDimensionDrafts = {};
    this.state.constraints = data?.constraints && typeof data.constraints === 'object' ? data.constraints : {};

    this.state.availablePresets = Array.isArray(data?.available_presets)
      ? data.available_presets.map((item) => ({
          key: item.key || item.name || '',
          name: item.name || '',
          group: item.group || 'system_preset',
          type: item.type || 'string',
          description: item.default_description || '',
          default_description: item.default_description || '',
          required: !!item.default_required,
          editable_description: item.editable_description !== false,
          restorable: item.restorable !== false,
          deletable: true,
          locked_name: item.locked_name !== false,
          locked_type: item.locked_type !== false,
          locked_required: item.locked_required !== false,
        }))
      : [];

    this.renderDimensions();
    this.renderScorePlaceholders();
    this.renderSchemaFieldsTable();
  },

  async loadPlaceholders() {
    const response = await fetch(`/admin-api/ai/ai-personality/${PERSONALITY_ID}/placeholders`);
    const data = await response.json();
    const list = Array.isArray(data) ? data : [];
    this.state.placeholders = list.map((p) => this.normalizePlaceholderRecord(p));
  },

  async loadStyles() {
    const response = await fetch('/qiao-dash/api/ai_style?limit=1000');
    const data = await response.json();
    const selector = document.getElementById('style-selector');

    // Filter for active styles - API returns status as string "Active" not number
    const activeStyles = (data.items || []).filter((s) => s.status === 'Active');
    // Create base options first
    activeStyles.forEach((style) => {
      const option = document.createElement('option');
      option.value = style.id;
      option.textContent = style.display_name || `ID ${style.id}`;
      selector.appendChild(option);
      this.state.styleOptionsMap[style.id] = option;
    });

    // Fetch dimensions for each style and update option label with truncated dimension names
    await Promise.all(
      activeStyles.map(async (style) => {
        try {
          const dims = await this.fetchDimensionsForStyle(style.id);
          const opt = this.state.styleOptionsMap[style.id];
          if (opt) {
            opt.textContent = this.formatStyleOptionText(style, dims);
          }
        } catch (_) {
          /* ignore per-option failure */
        }
      })
    );
  },

  // Build option label: "StyleName — dim1, dim2, dim3, ..."
  formatStyleOptionText(style, dims) {
    const base = (style.display_name || `ID ${style.id}` || '').toString();
    const list = Array.isArray(dims) ? dims : [];
    if (list.length === 0) return base;
    const names = list
      .map((d) => d.display_name || d.name)
      .filter(Boolean)
      .map(String);
    // Use count-based truncation for simplicity and stable width
    const maxCount = 3;
    let shown = names.slice(0, maxCount).join(', ');
    if (names.length > maxCount) shown += ', ...';
    return `${base} — ${shown}`;
  },

  // Fetch and cache a style's dimensions
  async fetchDimensionsForStyle(styleId) {
    if (this.state.styleDimensionsCache[styleId]) {
      return this.state.styleDimensionsCache[styleId];
    }
    const resp = await fetch(`/admin-api/ai/ai_style/${styleId}/dimensions`);
    const dims = await resp.json();
    const safe = Array.isArray(dims) ? dims : [];
    this.state.styleDimensionsCache[styleId] = safe;
    return safe;
  },

  replaceScoreDimensionEntries(dims) {
    const activeDimensionEntries = this.getScoreDimensionEntries();
    const activeByName = new Map();
    activeDimensionEntries.forEach((entry) => {
      const name = (entry.name || '').trim();
      if (!name) {
        return;
      }
      activeByName.set(name, entry);
    });

    const incomingNames = new Set((dims || []).map((dimension) => (dimension.name || '').trim()).filter(Boolean));
    activeDimensionEntries.forEach((entry) => {
      const name = (entry.name || '').trim();
      if (!name || incomingNames.has(name)) {
        return;
      }
      this.state.orphanScoreDimensionDrafts[name] = {
        description: entry.description || '',
      };
    });

    const nonDimensionEntries = this.state.fieldEntries.filter((entry) => entry.group !== 'score_dimension');
    const leadingEntries = nonDimensionEntries.filter(
      (entry) => entry.group === 'system_fixed' || entry.group === 'score_root'
    );
    const trailingEntries = nonDimensionEntries.filter(
      (entry) => entry.group !== 'system_fixed' && entry.group !== 'score_root'
    );
    const dimensionEntries = (dims || []).map((dimension) => {
      const name = (dimension.name || '').trim();
      const displayName = dimension.display_name || '';
      const defaultDescription = dimension.default_description || dimension.description || '';
      const existingActive = activeByName.get(name);
      const orphanDraft = this.state.orphanScoreDimensionDrafts[name];
      let description = defaultDescription;
      if (existingActive) {
        description = existingActive.description || '';
      } else if (orphanDraft) {
        description = orphanDraft.description || '';
      }
      delete this.state.orphanScoreDimensionDrafts[name];

      return {
        key: `score:${name}`,
        name,
        display_name: displayName,
        group: 'score_dimension',
        type: 'integer',
        required: true,
        description,
        default_description: defaultDescription,
        editable_description: true,
        restorable: true,
        deletable: false,
        locked_name: true,
        locked_type: true,
        locked_required: true,
        min: Number.isFinite(Number(dimension.min)) ? Number(dimension.min) : null,
        max: Number.isFinite(Number(dimension.max)) ? Number(dimension.max) : null,
        is_default: description === defaultDescription,
        exists: dimension.exists !== false,
      };
    });
    this.state.fieldEntries = [...leadingEntries, ...dimensionEntries, ...trailingEntries];
  },

  hasDimensionSetMismatch(candidateDims) {
    const currentNames = new Set(
      this.getScoreDimensionEntries()
        .map((dimension) => (dimension.name || '').trim())
        .filter(Boolean)
    );
    const candidateNames = new Set(
      (candidateDims || []).map((dimension) => (dimension.name || '').trim()).filter(Boolean)
    );
    if (currentNames.size !== candidateNames.size) {
      return true;
    }
    for (const name of candidateNames) {
      if (!currentNames.has(name)) {
        return true;
      }
    }
    return false;
  },

  renderStyleDimensionWarning(candidateDims) {
    const warning = document.getElementById('style-dimension-warning');
    if (!warning) {
      return;
    }
    const locked = !!this.state.constraints?.score_dimension_set_locked;
    const mismatch = this.hasDimensionSetMismatch(candidateDims);
    warning.classList.toggle('d-none', !(locked && mismatch));
  },

  showStyleSelector() {
    this.state.styleSelectorModal.show();
    // Render preview for currently selected style
    this.updateStylePreview().catch(() => {});
  },

  async loadStyleDimensions() {
    const styleId = document.getElementById('style-selector').value;
    if (!styleId) {
      alert('请选择style');
      return;
    }

    // Prefer cache to avoid duplicate requests
    const dims = await this.fetchDimensionsForStyle(styleId);
    this.renderStyleDimensionWarning(dims);
    this.replaceScoreDimensionEntries(
      (dims || []).map((dimension) => ({
        name: dimension.name || '',
        display_name: dimension.display_name || '',
        description: dimension.description || '',
        default_description: dimension.description || '',
        min: 0,
        max: 1000,
        is_default: true,
        exists: true,
      }))
    );

    this.renderDimensions();
    this.renderScorePlaceholders();
    this.renderSchemaFieldsTable();
    this.validatePrompt();
    this.state.styleSelectorModal.hide();
  },

  // Update the preview area in the modal with full dimension list
  async updateStylePreview() {
    const container = document.getElementById('style-dimensions-preview');
    const warning = document.getElementById('style-dimension-warning');
    if (!container) return;
    const styleId = document.getElementById('style-selector').value;
    if (!styleId) {
      container.innerHTML = '<small class="text-muted">请选择 style 查看维度</small>';
      if (warning) {
        warning.classList.add('d-none');
      }
      return;
    }

    try {
      const dims = await this.fetchDimensionsForStyle(styleId);
      if (!dims || dims.length === 0) {
        container.innerHTML =
          '<div class="alert alert-info py-1 mb-0"><i class="fas fa-info-circle me-2"></i>该 style 暂无维度</div>';
        if (warning) {
          warning.classList.add('d-none');
        }
        return;
      }
      const tableHtml =
        '<div class="table-responsive"><table class="table align-middle">' +
        '<thead><tr><th>Name</th><th>Display Name</th><th>Description</th></tr></thead><tbody>' +
        dims
          .map(
            (d) =>
              '<tr>' +
              '<td><code>' +
              this.escapeHtml(d.name || '') +
              '</code></td>' +
              '<td>' +
              this.escapeHtml(d.display_name || '-') +
              '</td>' +
              '<td>' +
              this.escapeHtml(d.description || '-') +
              '</td>' +
              '</tr>'
          )
          .join('') +
        '</tbody></table></div>';
      container.innerHTML = tableHtml;
      this.renderStyleDimensionWarning(dims);
    } catch (e) {
      container.innerHTML =
        '<div class="alert alert-warning py-1 mb-0"><i class="fas fa-exclamation-triangle me-2"></i>加载维度失败</div>';
      if (warning) {
        warning.classList.add('d-none');
      }
    }
  },

  renderDimensions() {
    const container = document.getElementById('dimensions-display');
    const dimensions = this.getScoreDimensionEntries();
    if (dimensions.length === 0) {
      container.innerHTML =
        '<p class="text-muted mb-0">请点击"从Style获取Dimension"按钮选择style并加载dimension信息</p>';
      return;
    }

    // Check for missing dimensions
    const missingDimensions = dimensions.filter((dimension) => !dimension.exists);
    let warningHtml = '';
    if (missingDimensions.length > 0) {
      const missingNames = missingDimensions.map((d) => '<code>' + this.escapeHtml(d.name) + '</code>').join(', ');
      warningHtml =
        '<div class="alert alert-danger d-flex align-items-center mb-3 py-1"><i class="fas fa-exclamation-triangle"></i><span><strong>警告:</strong> 以下维度在系统中不存在: ' +
        missingNames +
        '</span></div>';
    }

    const tableHtml =
      '<div class="table-responsive"><table class="table align-middle"><thead><tr><th>Name</th><th>Display Name</th><th>Description</th><th>Score Min</th><th>Score Max</th></tr></thead><tbody>' +
      dimensions
        .map((d, idx) => {
          const rowClass = d.exists ? '' : ' class="table-danger"';
          const minValue = Number.isFinite(d.min) ? d.min : '';
          const maxValue = Number.isFinite(d.max) ? d.max : '';
          return (
            '<tr' +
            rowClass +
            '>' +
            '<td><code>' +
            this.escapeHtml(d.name) +
            '</code></td>' +
            '<td>' +
            this.escapeHtml(d.display_name || '-') +
            '</td>' +
            '<td>' +
            this.escapeHtml(d.description || d.default_description || '-') +
            '</td>' +
            '<td><input type="number" class="form-control dimension-min" data-index="' +
            idx +
            '" value="' +
            this.escapeHtml(minValue) +
            '"></td>' +
            '<td><input type="number" class="form-control dimension-max" data-index="' +
            idx +
            '" value="' +
            this.escapeHtml(maxValue) +
            '"></td>' +
            '</tr>'
          );
        })
        .join('') +
      '</tbody></table></div>';

    container.innerHTML = warningHtml + tableHtml;
    container.querySelectorAll('.dimension-min').forEach((input) => {
      input.addEventListener('input', (event) => {
        const index = Number.parseInt(event.target.dataset.index, 10);
        const dim = dimensions[index];
        if (!dim) return;
        const value = Number(event.target.value);
        dim.min = Number.isFinite(value) ? value : null;
      });
    });
    container.querySelectorAll('.dimension-max').forEach((input) => {
      input.addEventListener('input', (event) => {
        const index = Number.parseInt(event.target.dataset.index, 10);
        const dim = dimensions[index];
        if (!dim) return;
        const value = Number(event.target.value);
        dim.max = Number.isFinite(value) ? value : null;
      });
    });
  },
};
