function t(i18n, key, fallback) {
  const value = i18n && Object.prototype.hasOwnProperty.call(i18n, key) ? i18n[key] : null;
  if (typeof value === 'string' && value.length > 0) {
    return value;
  }
  return fallback;
}

function parseConfigPayload(rawValue) {
  if (!rawValue) {
    return '';
  }
  try {
    return JSON.parse(rawValue);
  } catch (error) {
    return rawValue;
  }
}

function normalizeCurrentConfigValue(value) {
  if (value === null || value === undefined) {
    return '';
  }
  if (typeof value === 'boolean') {
    return value ? 'true' : 'false';
  }
  if (typeof value === 'number') {
    return String(value);
  }
  if (typeof value === 'object') {
    return JSON.stringify(value);
  }
  return String(value);
}

function escapeHtmlAttribute(value) {
  return String(value).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function parseJsonScriptById(scriptId) {
  if (!scriptId) {
    return '';
  }
  const node = document.getElementById(scriptId);
  if (!node) {
    return '';
  }
  return parseConfigPayload((node.textContent || '').trim());
}

function normalizeArrayEditorItem(item) {
  if (item === null || item === undefined) {
    return '';
  }
  if (typeof item === 'string') {
    return item.trim();
  }
  if (typeof item === 'number' || typeof item === 'boolean') {
    return String(item);
  }
  if (typeof item === 'object') {
    return JSON.stringify(item);
  }
  return String(item).trim();
}

function normalizeArrayPayload(value) {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.map((item) => normalizeArrayEditorItem(item)).filter((item) => item !== '');
}

function getScalarConfigKey(inputId) {
  return inputId.replace('config_modify_', '');
}

function getScalarClearFlag(inputId) {
  const configKey = getScalarConfigKey(inputId);
  return document.getElementById(`config_clear_${configKey}`);
}

function getScalarCurrentValueEl(configKey) {
  return document.querySelector(`[data-current-${configKey}]`);
}

function cacheScalarCurrentValueSnapshot(currentValueEl) {
  if (!currentValueEl.dataset.originalClassName) {
    currentValueEl.dataset.originalClassName = currentValueEl.className;
  }
  if (!currentValueEl.dataset.originalInnerHtml) {
    currentValueEl.dataset.originalInnerHtml = currentValueEl.innerHTML;
  }
}

function setScalarDeleteButtonState(inputId, isDeleted) {
  const deleteButton = document.querySelector(`[data-clear-target="${inputId}"]`);
  if (!deleteButton) {
    return;
  }
  deleteButton.classList.toggle('btn-outline-danger', !isDeleted);
  deleteButton.classList.toggle('btn-danger', isDeleted);
  deleteButton.setAttribute('aria-pressed', isDeleted ? 'true' : 'false');
}

function setScalarDeleteState(inputId, isDeleted) {
  const configKey = getScalarConfigKey(inputId);
  const clearFlag = getScalarClearFlag(inputId);
  if (clearFlag) {
    clearFlag.value = isDeleted ? '1' : '';
  }

  const currentValueEl = getScalarCurrentValueEl(configKey);
  if (currentValueEl) {
    cacheScalarCurrentValueSnapshot(currentValueEl);
    if (isDeleted) {
      currentValueEl.className = currentValueEl.dataset.originalClassName || currentValueEl.className;
      currentValueEl.classList.remove('text-primary', 'text-success');
      currentValueEl.classList.add('text-danger');
    } else {
      currentValueEl.className = currentValueEl.dataset.originalClassName || currentValueEl.className;
      currentValueEl.innerHTML = currentValueEl.dataset.originalInnerHtml || '';
    }
  }

  setScalarDeleteButtonState(inputId, isDeleted);
}

function getArrayCurrentList(editor) {
  const currentListId = editor.dataset.arrayCurrentListId;
  if (!currentListId) {
    return null;
  }
  return document.getElementById(currentListId);
}

function resolveArrayDefaultItem(editor) {
  const parsedValue = parseJsonScriptById(editor.dataset.arrayDefaultItemId || '');
  if (parsedValue === null || parsedValue === undefined) {
    return '';
  }
  return normalizeArrayEditorItem(parsedValue);
}

function getArrayValueType(editor) {
  const raw = Number.parseInt(editor.dataset.arrayValueType || '1', 10);
  if (Number.isNaN(raw)) {
    return 1;
  }
  return raw;
}

function getArrayAllowedValues(editor) {
  const raw = parseJsonScriptById(editor.dataset.arrayAllowedValuesId || '');
  if (!Array.isArray(raw)) {
    return [];
  }
  return raw.map((item) => String(item));
}

function getArrayCurrentValues(editor) {
  const raw = parseJsonScriptById(editor.dataset.arrayCurrentValueId || '');
  return normalizeArrayPayload(raw);
}

function getArrayInputPlaceholder(i18n, valueType, isExisting) {
  if (isExisting) {
    if (valueType === 4) {
      return t(i18n, 'leaveEmptyNoChangeExample', 'Leave empty for no change. Example: ["value1","value2"]');
    }
    return t(i18n, 'leaveEmptyNoChange', 'Leave empty for no change');
  }
  if (valueType === 4) {
    return t(i18n, 'enterJsonItem', 'Enter JSON item');
  }
  return t(i18n, 'enterValue', 'Enter value');
}

function getArraySelectEmptyLabel(i18n, isExisting) {
  return isExisting ? t(i18n, 'noChangeOption', '-- No Change --') : t(i18n, 'selectOption', '-- Select --');
}

function buildArrayEditorInput(editor, i18n, item, { isExisting = false } = {}) {
  const safeValue = escapeHtmlAttribute(item);
  const valueType = getArrayValueType(editor);
  const selectEmptyLabel = getArraySelectEmptyLabel(i18n, isExisting);
  if (valueType === 3) {
    const normalized = String(item).toLowerCase();
    return `
      <select class="form-select" data-array-item-input>
        <option value="">${selectEmptyLabel}</option>
        <option value="true" ${normalized === 'true' ? 'selected' : ''}>true</option>
        <option value="false" ${normalized === 'false' ? 'selected' : ''}>false</option>
      </select>
    `;
  }

  if (valueType === 5) {
    const options = getArrayAllowedValues(editor).map((option) => {
      const safeOption = escapeHtmlAttribute(option);
      const selected = option === item ? 'selected' : '';
      return `<option value="${safeOption}" ${selected}>${safeOption}</option>`;
    });
    return `
      <select class="form-select" data-array-item-input>
        <option value="">${selectEmptyLabel}</option>
        ${options.join('')}
      </select>
    `;
  }

  if (valueType === 2) {
    const placeholder = getArrayInputPlaceholder(i18n, valueType, isExisting);
    return `
      <input
        type="number"
        class="form-control"
        value="${safeValue}"
        placeholder="${placeholder}"
        data-array-item-input
      >
    `;
  }

  const placeholder = getArrayInputPlaceholder(i18n, valueType, isExisting);
  return `
    <input
      type="text"
      class="form-control"
      value="${safeValue}"
      placeholder="${placeholder}"
      data-array-item-input
    >
  `;
}

function buildArrayCurrentRow(editor, item, { isNew = false, isDeleted = false } = {}) {
  if (isNew) {
    return `
      <div class="array-current-row">
        <strong class="config-current-value text-muted fst-italic mb-0">(new item)</strong>
      </div>
    `;
  }
  if (isDeleted) {
    const normalizedDeleted = normalizeArrayEditorItem(item);
    if (normalizedDeleted === '') {
      return `
        <div class="array-current-row">
          <strong class="config-current-value text-muted fst-italic mb-0">(not set)</strong>
        </div>
      `;
    }
    return `
      <div class="array-current-row">
        <strong class="config-current-value text-danger mb-0">${escapeHtmlAttribute(normalizedDeleted)}</strong>
      </div>
    `;
  }
  const normalized = normalizeArrayEditorItem(item);
  if (normalized === '') {
    return `
      <div class="array-current-row">
        <strong class="config-current-value text-muted fst-italic mb-0">(not set)</strong>
      </div>
    `;
  }
  const defaultItem = resolveArrayDefaultItem(editor);
  const valueClass = normalized === defaultItem ? 'text-success' : 'text-primary';
  return `
    <div class="array-current-row">
      <strong class="config-current-value ${valueClass} mb-0">${escapeHtmlAttribute(normalized)}</strong>
    </div>
  `;
}

function buildArrayEditorRow(editor, i18n, rowModel) {
  const inputValue = rowModel.inputValue || '';
  const originalValue = rowModel.originalValue || '';
  const isExisting = rowModel.isExisting === true;
  const isDeleted = rowModel.isDeleted === true;
  return `
    <div
      class="array-editor-row"
      data-array-editor-row
      data-array-row-existing="${isExisting ? '1' : '0'}"
      data-array-row-deleted="${isDeleted ? '1' : '0'}"
      data-array-original-value="${escapeHtmlAttribute(originalValue)}"
    >
      <div class="input-group">
        ${buildArrayEditorInput(editor, i18n, inputValue, { isExisting })}
        <button type="button" class="btn btn-outline-secondary" data-array-use-current-row title="Use current value">
          <i class="fa fa-copy"></i>
        </button>
        <button type="button" class="btn btn-outline-secondary" data-array-fill-default-row title="Fill with default">
          <i class="fa fa-undo"></i>
        </button>
        <button type="button" class="btn ${
          isDeleted ? 'btn-danger' : 'btn-outline-danger'
        }" data-array-remove-row title="Toggle delete state" aria-pressed="${isDeleted ? 'true' : 'false'}">
          <i class="fa fa-trash"></i>
        </button>
      </div>
    </div>
  `;
}

function renderArrayEditorRows(editor, i18n, rowModels) {
  const rowsContainer = editor.querySelector('[data-array-editor-rows]');
  if (!rowsContainer) {
    return;
  }
  rowsContainer.innerHTML = rowModels.map((row) => buildArrayEditorRow(editor, i18n, row)).join('');
}

function renderArrayCurrentRows(editor, rowModels) {
  const currentList = getArrayCurrentList(editor);
  if (!currentList) {
    return;
  }
  currentList.innerHTML = rowModels
    .map((row) => {
      if (row.isExisting) {
        if (row.isDeleted) {
          return buildArrayCurrentRow(editor, row.originalValue, { isDeleted: true });
        }
        return buildArrayCurrentRow(editor, row.originalValue);
      }
      return buildArrayCurrentRow(editor, '', { isNew: true });
    })
    .join('');
}

function areArrayItemsEqual(left, right) {
  if (left.length !== right.length) {
    return false;
  }
  return left.every((item, index) => item === right[index]);
}

function setArrayDeleteButtonState(button, isDeleted) {
  if (!button) {
    return;
  }
  button.classList.toggle('btn-outline-danger', !isDeleted);
  button.classList.toggle('btn-danger', isDeleted);
  button.setAttribute('aria-pressed', isDeleted ? 'true' : 'false');
}

function getArrayRowMeta(row) {
  return {
    isExisting: row.dataset.arrayRowExisting === '1',
    isDeleted: row.dataset.arrayRowDeleted === '1',
    originalValue: normalizeArrayEditorItem(row.dataset.arrayOriginalValue || ''),
  };
}

function getArrayRowIndex(editor, row) {
  const rowsContainer = editor.querySelector('[data-array-editor-rows]');
  if (!rowsContainer) {
    return -1;
  }
  const rowNodes = Array.from(rowsContainer.querySelectorAll('[data-array-editor-row]'));
  return rowNodes.indexOf(row);
}

function setArrayRowDeleteState(editor, row, isDeleted) {
  row.dataset.arrayRowDeleted = isDeleted ? '1' : '0';
  const deleteButton = row.querySelector('[data-array-remove-row]');
  setArrayDeleteButtonState(deleteButton, isDeleted);

  const currentList = getArrayCurrentList(editor);
  const rowIndex = getArrayRowIndex(editor, row);
  if (!currentList || rowIndex < 0) {
    return;
  }
  const currentRows = Array.from(currentList.children);
  const pairedCurrentRow = currentRows[rowIndex];
  if (!pairedCurrentRow) {
    return;
  }

  const meta = getArrayRowMeta(row);
  pairedCurrentRow.outerHTML = meta.isExisting
    ? isDeleted
      ? buildArrayCurrentRow(editor, meta.originalValue, { isDeleted: true })
      : buildArrayCurrentRow(editor, meta.originalValue)
    : buildArrayCurrentRow(editor, '', { isNew: true });
}

function collectArrayFinalValues(editor) {
  const rows = Array.from(editor.querySelectorAll('[data-array-editor-row]'));
  const finalValues = [];
  rows.forEach((row) => {
    const meta = getArrayRowMeta(row);
    const input = row.querySelector('[data-array-item-input]');
    const inputValue = input ? (input.value || '').trim() : '';
    if (meta.isDeleted && inputValue === '') {
      return;
    }
    if (inputValue !== '') {
      finalValues.push(inputValue);
      return;
    }
    if (meta.isExisting && meta.originalValue !== '') {
      finalValues.push(meta.originalValue);
    }
  });
  return finalValues;
}

function syncArrayEditor(editor) {
  const hiddenInputId = editor.dataset.hiddenInputId;
  if (!hiddenInputId) {
    return;
  }
  const hiddenInput = document.getElementById(hiddenInputId);
  if (!hiddenInput) {
    return;
  }
  const initialItems = getArrayCurrentValues(editor);
  const finalValues = collectArrayFinalValues(editor);
  hiddenInput.value = areArrayItemsEqual(finalValues, initialItems) ? '' : JSON.stringify(finalValues);
}

function setupArrayEditor(editor, i18n) {
  const initialItems = getArrayCurrentValues(editor);
  const initialRows =
    initialItems.length > 0
      ? initialItems.map((item) => ({
          inputValue: '',
          originalValue: item,
          isExisting: true,
          isDeleted: false,
        }))
      : [
          {
            inputValue: '',
            originalValue: '',
            isExisting: false,
            isDeleted: false,
          },
        ];

  renderArrayCurrentRows(editor, initialRows);
  renderArrayEditorRows(editor, i18n, initialRows);
  syncArrayEditor(editor);

  const markDirtyAndSync = () => {
    editor.dataset.arrayDirty = 'true';
    syncArrayEditor(editor);
  };

  editor.addEventListener('input', (event) => {
    if (event.target instanceof Element && event.target.matches('[data-array-item-input]')) {
      const row = event.target.closest('[data-array-editor-row]');
      if (row instanceof HTMLElement) {
        const meta = getArrayRowMeta(row);
        if (meta.isDeleted && (event.target.value || '').trim() !== '') {
          setArrayRowDeleteState(editor, row, false);
        }
      }
      markDirtyAndSync();
    }
  });

  editor.addEventListener('change', (event) => {
    if (event.target instanceof Element && event.target.matches('[data-array-item-input]')) {
      const row = event.target.closest('[data-array-editor-row]');
      if (row instanceof HTMLElement) {
        const meta = getArrayRowMeta(row);
        if (meta.isDeleted && (event.target.value || '').trim() !== '') {
          setArrayRowDeleteState(editor, row, false);
        }
      }
      markDirtyAndSync();
    }
  });

  editor.addEventListener('click', (event) => {
    if (!(event.target instanceof Element)) {
      return;
    }
    const target = event.target.closest('button');
    if (!target) {
      return;
    }

    if (target.hasAttribute('data-array-add-row')) {
      event.preventDefault();
      const rowsContainer = editor.querySelector('[data-array-editor-rows]');
      const currentList = getArrayCurrentList(editor);
      if (!rowsContainer || !currentList) {
        return;
      }
      rowsContainer.insertAdjacentHTML(
        'beforeend',
        buildArrayEditorRow(editor, i18n, {
          inputValue: '',
          originalValue: '',
          isExisting: false,
          isDeleted: false,
        })
      );
      currentList.insertAdjacentHTML('beforeend', buildArrayCurrentRow(editor, '', { isNew: true }));
      markDirtyAndSync();
      const input = rowsContainer.lastElementChild?.querySelector('[data-array-item-input]');
      if (input) {
        input.focus();
      }
      return;
    }

    if (target.hasAttribute('data-array-remove-row')) {
      event.preventDefault();
      const row = target.closest('[data-array-editor-row]');
      const rowsContainer = editor.querySelector('[data-array-editor-rows]');
      const currentList = getArrayCurrentList(editor);
      if (!rowsContainer || !currentList || !row) {
        return;
      }
      const meta = getArrayRowMeta(row);
      const rowNodes = Array.from(rowsContainer.querySelectorAll('[data-array-editor-row]'));
      const rowIndex = rowNodes.indexOf(row);
      if (rowIndex < 0) {
        return;
      }
      if (!meta.isExisting) {
        row.remove();
        const currentRows = Array.from(currentList.children);
        const pairedCurrentRow = currentRows[rowIndex];
        if (pairedCurrentRow) {
          pairedCurrentRow.remove();
        }
        const hasRows = rowsContainer.querySelector('[data-array-editor-row]');
        if (!hasRows) {
          rowsContainer.insertAdjacentHTML(
            'beforeend',
            buildArrayEditorRow(editor, i18n, {
              inputValue: '',
              originalValue: '',
              isExisting: false,
              isDeleted: false,
            })
          );
          currentList.innerHTML = buildArrayCurrentRow(editor, '', { isNew: true });
        }
        markDirtyAndSync();
        return;
      }
      setArrayRowDeleteState(editor, row, !meta.isDeleted);
      markDirtyAndSync();
      return;
    }

    if (target.hasAttribute('data-array-use-current-row')) {
      event.preventDefault();
      const row = target.closest('[data-array-editor-row]');
      if (!row) {
        return;
      }
      const meta = getArrayRowMeta(row);
      const input = row.querySelector('[data-array-item-input]');
      if (!input) {
        return;
      }
      input.value = meta.originalValue;
      if (meta.isDeleted && meta.originalValue !== '') {
        setArrayRowDeleteState(editor, row, false);
      }
      markDirtyAndSync();
      return;
    }

    if (target.hasAttribute('data-array-fill-default-row')) {
      event.preventDefault();
      const defaultItem = resolveArrayDefaultItem(editor);
      const row = target.closest('[data-array-editor-row]');
      if (!row) {
        return;
      }
      const input = row.querySelector('[data-array-item-input]');
      if (!input) {
        return;
      }
      input.value = defaultItem;
      const meta = getArrayRowMeta(row);
      if (meta.isDeleted && defaultItem !== '') {
        setArrayRowDeleteState(editor, row, false);
      }
      markDirtyAndSync();
    }
  });
}

function setupConfigChangeConfirmation(i18n) {
  const saveButton = document.getElementById('save-settings-btn');
  if (!saveButton) {
    return;
  }
  saveButton.addEventListener('click', (event) => {
    const changes = [];
    document.querySelectorAll('[name^="config_modify_"]').forEach((input) => {
      const value = input.value ? input.value.trim() : '';
      const key = input.name.replace('config_modify_', '');
      const currentValueEl = document.querySelector(`[data-current-${key}]`);
      const currentValue = currentValueEl ? currentValueEl.textContent.trim() : '';
      if (value) {
        changes.push({
          key: key.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase()),
          from: currentValue,
          to: value,
        });
        return;
      }
      const clearFlag = document.getElementById(`config_clear_${key}`);
      if (clearFlag && clearFlag.value === '1') {
        changes.push({
          key: key.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase()),
          from: currentValue,
          to: '<cleared>',
        });
      }
    });

    if (changes.length === 0) {
      event.preventDefault();
      window.alert(t(i18n, 'noChanges', 'No changes to save. All modification fields are empty.'));
      return;
    }

    const message = `${t(
      i18n,
      'changeConfirmTitle',
      'You are about to modify the following configuration(s):'
    )}\n\n${changes.map((change) => `• ${change.key}: ${change.from} → ${change.to}`).join('\n')}\n\n${t(
      i18n,
      'changeConfirmQuestion',
      'Are you sure you want to save these changes?'
    )}`;

    if (!window.confirm(message)) {
      event.preventDefault();
    }
  });
}

function setupScalarInputs(i18n) {
  document.querySelectorAll('[data-copy-current-btn="true"]').forEach((button) => {
    button.addEventListener('click', () => {
      const target = button.dataset.copyCurrentTarget;
      const rawValue = button.dataset.copyCurrentValue || '';
      if (!target) {
        return;
      }
      const input = document.getElementById(target);
      if (!input) {
        return;
      }
      const normalizedValue = normalizeCurrentConfigValue(parseConfigPayload(rawValue));
      if (input.tagName === 'SELECT') {
        const hasOption = Array.from(input.options).some((option) => option.value === normalizedValue);
        if (!hasOption && normalizedValue !== '') {
          window.alert(t(i18n, 'currentValueNotSelectable', 'Current value is not available in selectable options.'));
          return;
        }
      }
      input.value = normalizedValue;
      input.dispatchEvent(new Event('input', { bubbles: true }));
      input.focus();
      setScalarDeleteState(target, false);
    });
  });

  document.querySelectorAll('[data-reset-default-btn="true"]').forEach((button) => {
    button.addEventListener('click', () => {
      const target = button.dataset.resetTarget;
      const rawValue = button.dataset.resetValue || '';
      if (!target) {
        return;
      }
      const input = document.getElementById(target);
      if (!input) {
        return;
      }
      input.value = normalizeCurrentConfigValue(parseConfigPayload(rawValue));
      input.dispatchEvent(new Event('input', { bubbles: true }));
      input.focus();
      setScalarDeleteState(target, false);
    });
  });

  document.querySelectorAll('[data-clear-input-btn="true"]').forEach((button) => {
    button.addEventListener('click', () => {
      const target = button.dataset.clearTarget;
      if (!target) {
        return;
      }
      const input = document.getElementById(target);
      if (!input) {
        return;
      }
      const clearFlag = getScalarClearFlag(target);
      const nextDeleted = !clearFlag || clearFlag.value !== '1';
      setScalarDeleteState(target, nextDeleted);
      input.focus();
    });
  });

  document.querySelectorAll('[name^="config_modify_"]').forEach((input) => {
    if (!input.id || !input.id.startsWith('config_modify_')) {
      return;
    }
    const resetDeleteStateOnInput = () => {
      const value = input.value ? input.value.trim() : '';
      if (value !== '') {
        setScalarDeleteState(input.id, false);
      }
    };
    input.addEventListener('input', resetDeleteStateOnInput);
    input.addEventListener('change', resetDeleteStateOnInput);
  });
}

function setupQuickNav() {
  const navToggle = document.getElementById('settings-nav-toggle');
  const navPanel = document.getElementById('settings-nav-panel');
  const navLinks = Array.from(document.querySelectorAll('.settings-nav-link'));
  const groupCards = Array.from(document.querySelectorAll('.config-group-card'));
  let activeGroupKey = '';

  function setQuickNavOpen(isOpen) {
    if (!navPanel || !navToggle) {
      return;
    }
    navPanel.hidden = !isOpen;
    navToggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
  }

  function highlightActiveGroup(groupKey) {
    if (!groupKey || groupKey === activeGroupKey) {
      return;
    }
    activeGroupKey = groupKey;
    let activeLink = null;
    navLinks.forEach((link) => {
      const isActive = link.dataset.targetGroup === groupKey;
      link.classList.toggle('active', isActive);
      if (isActive) {
        activeLink = link;
      }
    });
    if (activeLink) {
      activeLink.scrollIntoView({ block: 'nearest', inline: 'nearest' });
    }
  }

  function updateActiveGroupByViewport() {
    if (groupCards.length === 0 || navLinks.length === 0) {
      return;
    }
    const anchorY = Math.max(120, window.innerHeight * 0.3);
    let currentCard = groupCards[0];
    groupCards.forEach((card) => {
      if (card.getBoundingClientRect().top <= anchorY) {
        currentCard = card;
      }
    });
    highlightActiveGroup(currentCard.dataset.groupKey || '');
  }

  if (navToggle && navPanel) {
    navToggle.addEventListener('click', () => {
      setQuickNavOpen(navPanel.hidden);
    });
    navLinks.forEach((link) => {
      link.addEventListener('click', (event) => {
        event.preventDefault();
        const targetId = link.getAttribute('href');
        if (!targetId) {
          return;
        }
        const target = document.querySelector(targetId);
        if (!target) {
          return;
        }
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        highlightActiveGroup(link.dataset.targetGroup || '');
      });
    });
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') {
        setQuickNavOpen(false);
      }
    });
  }

  if (groupCards.length > 0 && navLinks.length > 0) {
    updateActiveGroupByViewport();
    window.addEventListener('scroll', updateActiveGroupByViewport, { passive: true });
    window.addEventListener('resize', updateActiveGroupByViewport);
  }
}

async function postJson(url, method) {
  const response = await fetch(url, { method });
  let data = null;
  try {
    data = await response.json();
  } catch (error) {
    data = null;
  }
  return { ok: response.ok, data };
}

function setupSystemManagementActions(config, i18n) {
  const conversationId = config.conversationId || '';
  const webhookUrl = config.webhookUrl || '';
  const api = config.api || {};

  document.querySelectorAll('[data-system-action]').forEach((button) => {
    button.addEventListener('click', async () => {
      const action = button.getAttribute('data-system-action');
      if (action === 'copy-conversation-id') {
        try {
          await navigator.clipboard.writeText(conversationId);
          window.alert(t(i18n, 'conversationIdCopied', 'Conversation ID copied!'));
        } catch (error) {
          window.alert(t(i18n, 'copyFailed', 'Failed to copy'));
        }
        return;
      }

      if (action === 'copy-webhook-url') {
        try {
          await navigator.clipboard.writeText(webhookUrl);
          window.alert(t(i18n, 'webhookCopied', 'Webhook URL copied to clipboard!'));
        } catch (error) {
          window.alert(t(i18n, 'copyUrlFailed', 'Failed to copy URL'));
        }
        return;
      }

      if (action === 'regenerate-conversation') {
        const confirmed = window.confirm(
          t(
            i18n,
            'confirmRegenerateConversation',
            'WARNING: This will create a new system conversation and invalidate the old one.\n\nContinue?'
          )
        );
        if (!confirmed) {
          return;
        }
        try {
          const result = await postJson(api.refreshConversation, 'POST');
          if (result.ok && result.data && result.data.success) {
            window.alert(
              `✓ ${t(i18n, 'sysConversationRegenerated', 'System conversation regenerated successfully!')}\n\n${t(
                i18n,
                'newId',
                'New ID'
              )}: ${result.data.conversation_id}`
            );
            window.location.reload();
            return;
          }
          const detail = result.data && result.data.error ? result.data.error : '';
          window.alert(`✗ ${t(i18n, 'failedPrefix', 'Failed:')} ${detail}`);
        } catch (error) {
          window.alert(`✗ ${t(i18n, 'regenerateConversationFailed', 'Failed to regenerate conversation')}`);
        }
        return;
      }

      if (action === 'regenerate-webhook-token') {
        const confirmed = window.confirm(
          t(i18n, 'confirmRegenerateToken', 'WARNING: This will invalidate the current webhook URL.\n\nContinue?')
        );
        if (!confirmed) {
          return;
        }
        try {
          const result = await postJson(api.regenerateWebhookToken, 'POST');
          if (result.ok && result.data && result.data.success) {
            window.alert(
              `✓ ${t(i18n, 'tokenRegenerated', 'Token regenerated successfully!')}\n\n${
                result.data.warning || ''
              }\n\n${t(i18n, 'newWebhookLoaded', 'New webhook URL has been loaded.')}`
            );
            window.location.reload();
            return;
          }
          const detail =
            result.data && (result.data.error || result.data.detail)
              ? result.data.error || result.data.detail
              : t(i18n, 'unknownError', 'Unknown error');
          window.alert(`✗ ${t(i18n, 'failedPrefix', 'Failed:')} ${detail}`);
        } catch (error) {
          window.alert(`✗ ${t(i18n, 'regenerateTokenFailed', 'Failed to regenerate token')}`);
        }
      }
    });
  });
}

export function initSystemSettingsPage(config = {}) {
  const i18n = config.i18n || {};

  setupConfigChangeConfirmation(i18n);
  setupQuickNav();
  setupScalarInputs(i18n);
  document.querySelectorAll('[data-array-editor="true"]').forEach((editor) => {
    setupArrayEditor(editor, i18n);
  });

  if (config.pageMode === 'system') {
    setupSystemManagementActions(config, i18n);
  }
}
