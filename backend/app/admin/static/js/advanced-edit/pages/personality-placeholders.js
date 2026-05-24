const SYSTEM_PLACEHOLDERS = [
  { key: 'relationship_prompt', title: '关系提示词' },
  { key: 'self_profile', title: '自身资料描述' },
  { key: 'other_profile', title: '对方资料描述' },
  { key: 'current_datetime', title: '当前日期时间' },
  { key: 'memory', title: 'AI记忆' },
];

export const personalityPlaceholderMethods = {
  renderSystemPlaceholders() {
    const container = document.getElementById('system-placeholders');
    container.innerHTML = SYSTEM_PLACEHOLDERS.map(
      (p) =>
        `<button type="button" class="badge rounded-pill text-bg-primary placeholder-badge placeholder-btn" data-base="text-bg-primary" data-key="${encodeURIComponent(
          p.key
        )}" title="${this.escapeHtml(p.title)}">
        <i class="fas fa-plus me-1"></i>${this.escapeHtml(p.key)}
      </button>`
    ).join('');
    container.querySelectorAll('.placeholder-btn').forEach((button) => {
      button.addEventListener('click', () => this.insertPlaceholder(decodeURIComponent(button.dataset.key || '')));
    });
  },

  renderScorePlaceholders() {
    const container = document.getElementById('score-placeholders');
    const dimensions = this.getScoreDimensionEntries();
    if (dimensions.length === 0) {
      container.innerHTML = '<small class="text-muted mb-1">请先加载dimension信息</small>';
      return;
    }

    container.innerHTML = dimensions
      .map(
        (d) =>
          `<button type="button" class="badge rounded-pill text-bg-success placeholder-badge placeholder-btn" data-base="text-bg-success" data-key="${encodeURIComponent(
            'score:' + d.name
          )}" title="${this.escapeHtml((d.display_name || d.name) + ' 分数')}">
        <i class="fas fa-plus me-1"></i>score:${this.escapeHtml(d.name)}
      </button>`
      )
      .join('');
    container.querySelectorAll('.placeholder-btn').forEach((button) => {
      button.addEventListener('click', () => this.insertPlaceholder(decodeURIComponent(button.dataset.key || '')));
    });
  },

  renderCustomPlaceholders() {
    const container = document.getElementById('custom-placeholders');
    const valid = this.state.placeholders.filter((p) => this.isValidPlaceholderKey((p.placeholder_key || '').trim()));
    if (valid.length === 0) {
      container.innerHTML = '<small class="text-muted mb-1">暂无自定义placeholder</small>';
      return;
    }

    container.innerHTML = valid
      .map(
        (p) =>
          `<button type="button" class="badge rounded-pill text-bg-secondary placeholder-badge placeholder-btn" data-base="text-bg-secondary" data-key="${encodeURIComponent(
            p.placeholder_key
          )}">
        <i class="fas fa-plus me-1"></i>${this.escapeHtml(p.placeholder_key)}
      </button>`
      )
      .join('');
    container.querySelectorAll('.placeholder-btn').forEach((button) => {
      button.addEventListener('click', () => this.insertPlaceholder(decodeURIComponent(button.dataset.key || '')));
    });
  },

  isGlobalUniquePlaceholderKey(rawKey) {
    const key = typeof rawKey === 'string' ? rawKey.trim() : '';
    if (!key) {
      return false;
    }
    const configuredKeys = Array.isArray(this.state.globalUniquePlaceholderKeys)
      ? this.state.globalUniquePlaceholderKeys
      : [];
    return configuredKeys.includes(key);
  },

  renderPlaceholdersList() {
    const container = document.getElementById('placeholders-list');
    if (this.state.placeholders.length === 0) {
      container.innerHTML = '<p class="text-muted mb-0">还没有定义placeholder，请先创建一个。</p>';
      return;
    }

    const rows = this.state.placeholders.map((p) => {
      const clientId = this.escapeHtml(p.client_id || '');
      const keyValue = this.escapeHtml(p.placeholder_key || '');
      const displayNameValue = this.escapeHtml(p.display_name || '');
      const descriptionValue = this.escapeHtml(p.description || '');
      const exampleValueValue = this.escapeHtml(p.example_value || '');
      const requiredChecked = p.is_required ? 'checked' : '';
      const isGlobalUnique = this.isGlobalUniquePlaceholderKey(p.placeholder_key || '');
      const globalUniqueOverlay = isGlobalUnique
        ? '<span class="badge rounded-pill placeholder-key-global-unique">Unique</span>'
        : '';

      return `
        <tr data-client-id="${clientId}">
          <td style="min-width: 220px;">
            <div class="placeholder-key-field">
              <input
                type="text"
                class="form-control placeholder-input placeholder-key-input"
                value="${keyValue}"
                data-client-id="${clientId}"
                data-field="placeholder_key"
                placeholder="例如 nickname"
                inputmode="latin"
                autocomplete="off"
                spellcheck="false"
              >
              ${globalUniqueOverlay}
              <div class="invalid-feedback">Key 必须为 [A-Za-z0-9_]+ 且不可重复</div>
            </div>
          </td>
          <td style="min-width: 180px;">
            <input
              type="text"
              class="form-control placeholder-input"
              value="${displayNameValue}"
              data-client-id="${clientId}"
              data-field="display_name"
              placeholder="可选"
            >
          </td>
          <td style="min-width: 220px;">
            <input
              type="text"
              class="form-control placeholder-input"
              value="${descriptionValue}"
              data-client-id="${clientId}"
              data-field="description"
              placeholder="可选"
            >
          </td>
          <td style="min-width: 220px;">
            <input
              type="text"
              class="form-control placeholder-input"
              value="${exampleValueValue}"
              data-client-id="${clientId}"
              data-field="example_value"
              placeholder="可选"
            >
          </td>
          <td class="text-center" style="min-width: 90px;">
            <input
              type="checkbox"
              class="form-check-input placeholder-input"
              ${requiredChecked}
              data-client-id="${clientId}"
              data-field="is_required"
            >
          </td>
          <td>
            <button type="button" class="btn btn-outline-danger" data-action="delete-placeholder" data-client-id="${clientId}" title="删除">
              <i class="fas fa-trash"></i>
            </button>
          </td>
        </tr>
      `;
    });

    container.innerHTML = `
      <div class="table-responsive">
        <table class="table align-middle">
          <thead>
            <tr>
              <th>Key</th>
              <th>Display Name</th>
              <th>Description</th>
              <th>Example Value</th>
              <th class="text-center">Required</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>${rows.join('')}</tbody>
        </table>
      </div>
      <div class="text-muted small">
        Key 仅允许 <code>[A-Za-z0-9_]+</code>，且禁止以 <code>score:</code> 开头。<code>Unique</code> 标注来源于系统配置 <code>ai_global_unique_placeholder_keys</code>。
      </div>
    `;
  },

  nextPlaceholderClientId() {
    this.state.placeholderClientIdSeq += 1;
    return `ph_${Date.now()}_${this.state.placeholderClientIdSeq}`;
  },

  normalizePlaceholderRecord(raw) {
    const placeholder = raw && typeof raw === 'object' ? raw : {};
    const key = typeof placeholder.placeholder_key === 'string' ? placeholder.placeholder_key : '';
    return {
      id: placeholder.id ?? null,
      placeholder_key: key,
      display_name: typeof placeholder.display_name === 'string' ? placeholder.display_name : '',
      description: typeof placeholder.description === 'string' ? placeholder.description : '',
      example_value: typeof placeholder.example_value === 'string' ? placeholder.example_value : '',
      is_required: !!placeholder.is_required,
      client_id: this.nextPlaceholderClientId(),
      _last_committed_key: key,
    };
  },

  getPlaceholderByClientId(clientId) {
    return this.state.placeholders.find((p) => p.client_id === clientId) || null;
  },

  addPlaceholderRow() {
    const row = this.normalizePlaceholderRecord({
      id: null,
      placeholder_key: '',
      display_name: '',
      description: '',
      example_value: '',
      is_required: false,
    });
    this.state.placeholders.push(row);
    this.renderCustomPlaceholders();
    this.renderPlaceholdersList();
    this.validatePrompt();
    const keyInput = document.querySelector(`.placeholder-key-input[data-client-id="${row.client_id}"]`);
    keyInput?.focus();
  },

  bindPlaceholderListEvents() {
    const container = document.getElementById('placeholders-list');
    if (!container || container.dataset.bound === '1') {
      return;
    }
    container.dataset.bound = '1';

    container.addEventListener('input', (event) => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) return;
      const field = target.dataset?.field;
      const clientId = target.dataset?.clientId;
      if (!field || !clientId) return;
      const p = this.getPlaceholderByClientId(clientId);
      if (!p) return;

      if (field === 'is_required' && target instanceof HTMLInputElement) {
        p[field] = !!target.checked;
        return;
      }

      if (target instanceof HTMLInputElement) {
        p[field] = target.value;
      }
    });

    container.addEventListener('change', async (event) => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) return;
      const field = target.dataset?.field;
      const clientId = target.dataset?.clientId;
      if (!field || !clientId) return;
      if (field !== 'placeholder_key') return;

      const input = target instanceof HTMLInputElement ? target : null;
      if (!input) return;
      await this.commitPlaceholderKeyChange(clientId, input.value);
      this.applyPlaceholderKeyValidationStyles();
    });

    container.addEventListener('click', async (event) => {
      const target = event.target instanceof HTMLElement ? event.target.closest('[data-action]') : null;
      if (!target) return;
      const action = target.dataset?.action;
      const clientId = target.dataset?.clientId;
      if (action !== 'delete-placeholder' || !clientId) return;
      await this.deletePlaceholderByClientId(clientId);
    });
  },

  isValidPlaceholderKey(key) {
    if (typeof key !== 'string') return false;
    const trimmed = key.trim();
    if (!trimmed) return false;
    if (trimmed.startsWith('score:')) return false;
    return /^[A-Za-z0-9_]+$/.test(trimmed);
  },

  validatePlaceholders() {
    const errors = new Map();
    const seen = new Map();
    this.state.placeholders.forEach((p) => {
      const clientId = p.client_id;
      const key = (p.placeholder_key || '').trim();
      if (!this.isValidPlaceholderKey(key)) {
        errors.set(clientId, 'invalid_key');
        return;
      }
      if (seen.has(key)) {
        errors.set(clientId, 'duplicate_key');
        errors.set(seen.get(key), 'duplicate_key');
        return;
      }
      seen.set(key, clientId);
    });
    return errors;
  },

  applyPlaceholderKeyValidationStyles() {
    const errors = this.validatePlaceholders();
    document.querySelectorAll('.placeholder-key-input').forEach((el) => {
      const input = el instanceof HTMLInputElement ? el : null;
      if (!input) return;
      const clientId = input.dataset?.clientId;
      if (!clientId) return;
      input.classList.toggle('is-invalid', errors.has(clientId));
    });
  },

  async commitPlaceholderKeyChange(clientId, rawValue) {
    const p = this.getPlaceholderByClientId(clientId);
    if (!p) return;

    const nextKey = typeof rawValue === 'string' ? rawValue.trim() : '';
    const prevKey = (p._last_committed_key || '').trim();

    if (nextKey === prevKey) {
      p.placeholder_key = prevKey;
      return;
    }

    if (!this.isValidPlaceholderKey(nextKey)) {
      alert('Placeholder Key 不合法：仅允许 [A-Za-z0-9_]+，且禁止以 score: 开头');
      p.placeholder_key = prevKey;
      const input = document.querySelector(`.placeholder-key-input[data-client-id="${clientId}"]`);
      if (input instanceof HTMLInputElement) {
        input.value = prevKey;
        input.focus();
      }
      return;
    }

    const existsOther = this.state.placeholders.some(
      (item) => item.client_id !== clientId && (item.placeholder_key || '').trim() === nextKey
    );
    if (existsOther) {
      alert(`Placeholder Key 重复：${nextKey}`);
      p.placeholder_key = prevKey;
      const input = document.querySelector(`.placeholder-key-input[data-client-id="${clientId}"]`);
      if (input instanceof HTMLInputElement) {
        input.value = prevKey;
        input.focus();
      }
      return;
    }

    p.placeholder_key = nextKey;
    p._last_committed_key = nextKey;

    const editor = document.getElementById('prompt-editor');
    const oldPlaceholder = `{{${prevKey}}}`;
    const newPlaceholder = `{{${nextKey}}}`;
    const prompt = editor?.value || '';

    if (prevKey && prompt.includes(oldPlaceholder)) {
      const ok = await this.confirmAction({
        title: '确认替换提示词中的占位符',
        message: `检测到提示词模板中已存在 <code>${this.escapeHtml(
          oldPlaceholder
        )}</code>。<br>是否自动全量替换为 <code>${this.escapeHtml(newPlaceholder)}</code>？`,
        confirmText: '替换',
        cancelText: '不替换',
        confirmButtonClass: 'btn btn-primary',
      });
      if (ok && editor) {
        editor.value = prompt.replaceAll(oldPlaceholder, newPlaceholder);
      }
    }

    this.renderCustomPlaceholders();
    this.renderPlaceholdersList();
    this.validatePrompt();
    this.applyPlaceholderKeyValidationStyles();
  },

  async deletePlaceholderByClientId(clientId) {
    const p = this.getPlaceholderByClientId(clientId);
    if (!p) return;

    const key = (p.placeholder_key || '').trim() || '(空)';
    const ok = await this.confirmAction({
      title: '确认删除 Placeholder',
      message: `确认删除 <code>${this.escapeHtml(key)}</code> 吗？`,
      confirmText: '删除',
      cancelText: '取消',
      confirmButtonClass: 'btn btn-danger',
    });
    if (!ok) return;

    if (p.id) {
      this.state.deletedPlaceholderIds.push(p.id);
    }
    this.state.placeholders = this.state.placeholders.filter((item) => item.client_id !== clientId);

    this.renderCustomPlaceholders();
    this.renderPlaceholdersList();
    this.validatePrompt();
    this.applyPlaceholderKeyValidationStyles();
  },

  extractUsedPlaceholderKeysFromPrompt() {
    const prompt = document.getElementById('prompt-editor')?.value || '';
    const regex = /\{\{([^}]+)\}\}/g;
    const keys = new Set();
    let match;
    while ((match = regex.exec(prompt)) !== null) {
      const key = (match[1] || '').trim();
      if (key) keys.add(key);
    }
    return [...keys];
  },

  importUnknownPlaceholdersFromPrompt() {
    const usedKeys = this.extractUsedPlaceholderKeysFromPrompt();
    if (usedKeys.length === 0) {
      alert('提示词模板中未检测到任何 {{placeholder}}');
      return;
    }

    const known = new Set([
      ...SYSTEM_PLACEHOLDERS.map((p) => p.key),
      ...this.getScoreDimensionEntries().map((d) => `score:${d.name}`),
      ...this.state.placeholders
        .map((p) => (p.placeholder_key || '').trim())
        .filter((k) => this.isValidPlaceholderKey(k)),
    ]);

    const candidates = usedKeys.filter((k) => !known.has(k) && !k.startsWith('score:'));
    const valid = [];
    const invalid = [];
    candidates.forEach((k) => {
      if (this.isValidPlaceholderKey(k)) {
        valid.push(k);
      } else {
        invalid.push(k);
      }
    });

    if (valid.length === 0) {
      const msg =
        invalid.length > 0
          ? `未找到可导入的未知 placeholder。以下 key 因格式不合法被跳过：${invalid.join(', ')}`
          : '未找到可导入的未知 placeholder。';
      alert(msg);
      return;
    }

    valid.forEach((key) => {
      this.state.placeholders.push(
        this.normalizePlaceholderRecord({
          id: null,
          placeholder_key: key,
          display_name: '',
          description: '',
          example_value: '',
          is_required: true,
        })
      );
    });

    this.renderCustomPlaceholders();
    this.renderPlaceholdersList();
    this.validatePrompt();
    this.applyPlaceholderKeyValidationStyles();

    if (invalid.length > 0) {
      alert(`已导入 ${valid.length} 个未知 placeholder。以下 key 因格式不合法被跳过：${invalid.join(', ')}`);
    } else {
      alert(`已导入 ${valid.length} 个未知 placeholder。`);
    }
  },

  showGlobalUniqueImportModal() {
    const listContainer = document.getElementById('global-unique-import-list');
    if (!listContainer) {
      return;
    }

    const globalKeys = Array.isArray(this.state.globalUniquePlaceholderKeys)
      ? this.state.globalUniquePlaceholderKeys
      : [];
    const validKeys = globalKeys.filter((key) => this.isValidPlaceholderKey(key));
    const existingKeys = new Set(
      this.state.placeholders
        .map((placeholder) => (placeholder.placeholder_key || '').trim())
        .filter((key) => this.isValidPlaceholderKey(key))
    );

    if (validKeys.length === 0) {
      listContainer.innerHTML =
        '<div class="alert alert-info mb-0">系统配置未提供可导入的全局唯一 placeholder key。</div>';
      this.state.globalUniqueImportModal.show();
      return;
    }

    listContainer.innerHTML = validKeys
      .map((key) => {
        const isExisting = existingKeys.has(key);
        const disabled = isExisting ? 'disabled' : '';
        const hint = isExisting ? '<span class="text-muted small ms-2">已存在</span>' : '';
        return `
          <label class="form-check d-flex align-items-center mb-2">
            <input class="form-check-input me-2" type="checkbox" value="${this.escapeHtml(key)}" ${disabled}>
            <code>${this.escapeHtml(key)}</code>${hint}
          </label>
        `;
      })
      .join('');

    this.state.globalUniqueImportModal.show();
  },

  async confirmGlobalUniqueImport() {
    const listContainer = document.getElementById('global-unique-import-list');
    if (!listContainer) {
      return;
    }

    const selectedKeys = Array.from(listContainer.querySelectorAll('input[type="checkbox"]:checked')).map((input) =>
      input instanceof HTMLInputElement ? input.value.trim() : ''
    );
    if (selectedKeys.length === 0) {
      alert('请至少选择一个 placeholder key');
      return;
    }

    const existingKeys = new Set(
      this.state.placeholders
        .map((placeholder) => (placeholder.placeholder_key || '').trim())
        .filter((key) => this.isValidPlaceholderKey(key))
    );
    let importedCount = 0;
    selectedKeys.forEach((key) => {
      if (!key || existingKeys.has(key)) {
        return;
      }
      this.state.placeholders.push(
        this.normalizePlaceholderRecord({
          id: null,
          placeholder_key: key,
          display_name: '',
          description: '',
          example_value: '',
          is_required: true,
        })
      );
      existingKeys.add(key);
      importedCount += 1;
    });

    this.renderCustomPlaceholders();
    this.renderPlaceholdersList();
    this.validatePrompt();
    this.applyPlaceholderKeyValidationStyles();
    this.state.globalUniqueImportModal.hide();

    if (importedCount > 0) {
      alert(`已导入 ${importedCount} 个全局唯一 placeholder。`);
      return;
    }
    alert('所选 key 均已存在，未导入新项。');
  },

  insertPlaceholder(key) {
    if (typeof key !== 'string' || key.trim() === '') return;
    const editor = document.getElementById('prompt-editor');
    const placeholder = '{{' + key + '}}';
    editor.focus();
    try {
      const start = editor.selectionStart;
      const end = editor.selectionEnd;
      let usedExec = false;
      try {
        if (typeof document.queryCommandSupported === 'function' && document.queryCommandSupported('insertText')) {
          usedExec = document.execCommand('insertText', false, placeholder);
        }
      } catch {
        /* ignore */
      }
      if (!usedExec) {
        if (typeof editor.setRangeText === 'function') {
          editor.setRangeText(placeholder, start, end, 'end');
          // Track for manual undo since some browsers won't add to native stack
          this.state.manualUndoOps.push({ start, len: placeholder.length, text: placeholder });
        } else {
          // Fallback: manual insert
          const pos = start;
          const text = editor.value;
          editor.value = text.substring(0, pos) + placeholder + text.substring(end);
          editor.setSelectionRange(pos + placeholder.length, pos + placeholder.length);
          this.state.manualUndoOps.push({ start: pos, len: placeholder.length, text: placeholder });
        }
      }
    } catch {
      // Graceful fallback
      const pos = editor.selectionStart || editor.value.length;
      editor.value = editor.value.slice(0, pos) + placeholder + editor.value.slice(pos);
      editor.setSelectionRange(pos + placeholder.length, pos + placeholder.length);
      this.state.manualUndoOps.push({ start: pos, len: placeholder.length, text: placeholder });
    }
    this.validatePrompt();
  },

  validatePrompt() {
    const prompt = document.getElementById('prompt-editor').value;
    const regex = /\{\{([^}]+)\}\}/g;
    const used = {};
    let match;

    while ((match = regex.exec(prompt)) !== null) {
      const key = match[1].trim();
      used[key] = (used[key] || 0) + 1;
    }

    // Get all known placeholders
    const known = new Set([
      ...SYSTEM_PLACEHOLDERS.map((p) => p.key),
      ...this.getScoreDimensionEntries().map((d) => `score:${d.name}`),
      ...this.state.placeholders
        .map((p) => (p.placeholder_key || '').trim())
        .filter((k) => this.isValidPlaceholderKey(k)),
    ]);

    // Classify unknowns and score placeholder errors
    const usedKeys = Object.keys(used);
    const knownScore = new Set(this.getScoreDimensionEntries().map((d) => `score:${d.name}`));
    const invalidScoreFormat = usedKeys.filter((k) => k.startsWith('score:') && !/^score:[A-Za-z0-9_]+$/.test(k));
    const invalidScoreDim = usedKeys.filter((k) => /^score:[A-Za-z0-9_]+$/.test(k) && !knownScore.has(k));
    const unknown = usedKeys.filter((k) => !k.startsWith('score:') && !known.has(k));

    // Update warnings
    const container = document.getElementById('placeholder-warnings');
    const parts = [];
    if (invalidScoreFormat.length > 0) {
      parts.push(
        `<div class="alert alert-warning d-flex align-items-center mb-2 py-1"><i class="fas fa-exclamation-triangle"></i><span><strong>格式错误的分数placeholder:</strong> ${invalidScoreFormat
          .map((k) => `<code>{{${this.escapeHtml(k)}}}</code>`)
          .join(', ')}</span></div>`
      );
    }
    if (invalidScoreDim.length > 0) {
      parts.push(
        `<div class="alert alert-warning d-flex align-items-center mb-2 py-1"><i class="fas fa-exclamation-triangle"></i><span><strong>不存在的分数placeholder:</strong> ${invalidScoreDim
          .map((k) => `<code>{{${this.escapeHtml(k)}}}</code>`)
          .join(', ')}</span></div>`
      );
    }
    if (unknown.length > 0) {
      parts.push(
        `<div class="alert alert-warning d-flex align-items-center mb-0 py-1"><i class="fas fa-exclamation-triangle"></i><span><strong>未知placeholder:</strong> ${unknown
          .map((k) => `<code>{{${this.escapeHtml(k)}}}</code>`)
          .join(', ')}</span></div>`
      );
    }
    container.innerHTML = parts.join('');

    // Update badge states: 0=colored + plus, 1=fade + check, >1=red + warn
    document.querySelectorAll('.placeholder-btn').forEach((btn) => {
      const key = decodeURIComponent(btn.dataset.key || '');
      const count = used[key] || 0;
      const icon = btn.querySelector('i');

      const baseClasses = ['text-bg-primary', 'text-bg-success', 'text-bg-secondary'];
      const baseClass = btn.dataset.base || baseClasses.find((c) => btn.classList.contains(c));
      // Reset dynamic state
      btn.classList.remove('text-bg-danger');
      btn.style.opacity = '1';
      const countSpan = btn.querySelector('.count');
      if (countSpan) countSpan.remove();

      if (count === 0) {
        // Not added: keep strong color + plus
        baseClasses.forEach((c) => btn.classList.remove(c));
        if (baseClass) btn.classList.add(baseClass);
        icon.className = 'fas fa-plus me-1';
      } else if (count === 1) {
        // Added once: fade base color + check
        baseClasses.forEach((c) => btn.classList.remove(c));
        if (baseClass) btn.classList.add(baseClass);
        btn.style.opacity = '0.6';
        icon.className = 'fas fa-check me-1';
      } else {
        // Added many: danger red + count
        baseClasses.forEach((c) => btn.classList.remove(c));
        btn.classList.add('text-bg-danger');
        icon.className = 'fas fa-exclamation-triangle me-1';
        btn.insertAdjacentHTML('beforeend', `<span class=\"count ms-1\">(${count}次)</span>`);
      }
    });
  },
};
