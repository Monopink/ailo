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
  } catch {
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

function padDateTimePart(value) {
  return String(value).padStart(2, '0');
}

function formatDateTimeForPicker(date) {
  const year = date.getFullYear();
  const month = padDateTimePart(date.getMonth() + 1);
  const day = padDateTimePart(date.getDate());
  const hours = padDateTimePart(date.getHours());
  const minutes = padDateTimePart(date.getMinutes());
  const seconds = padDateTimePart(date.getSeconds());
  return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
}

function isoToPickerDateTimeValue(value) {
  if (typeof value !== 'string' || value.trim() === '') {
    return '';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return '';
  }
  return formatDateTimeForPicker(date);
}

function parsePickerDateTime(value) {
  if (typeof value !== 'string' || value.trim() === '') {
    return null;
  }
  const normalized = value.trim();

  if (typeof window.flatpickr === 'function') {
    const parsedByFlatpickr = window.flatpickr.parseDate(normalized, 'Y-m-d H:i:S');
    if (parsedByFlatpickr instanceof Date && !Number.isNaN(parsedByFlatpickr.getTime())) {
      return parsedByFlatpickr;
    }
    const parsedByFlatpickrNoSeconds = window.flatpickr.parseDate(normalized, 'Y-m-d H:i');
    if (parsedByFlatpickrNoSeconds instanceof Date && !Number.isNaN(parsedByFlatpickrNoSeconds.getTime())) {
      return parsedByFlatpickrNoSeconds;
    }
  }

  const fallbackInput = normalized.includes(' ') ? normalized.replace(' ', 'T') : normalized;
  const date = new Date(fallbackInput);
  if (Number.isNaN(date.getTime())) {
    return null;
  }
  return date;
}

function pickerDateTimeToIso(input, value) {
  const parsed = parsePickerDateTime(value);
  if (parsed instanceof Date) {
    return parsed.toISOString();
  }

  const selected =
    input &&
    input._flatpickr &&
    Array.isArray(input._flatpickr.selectedDates) &&
    input._flatpickr.selectedDates.length > 0
      ? input._flatpickr.selectedDates[0]
      : null;
  if (selected instanceof Date && !Number.isNaN(selected.getTime())) {
    return selected.toISOString();
  }
  return '';
}

function setPickerInputValue(input, value) {
  const normalized = isoToPickerDateTimeValue(value);
  if (input && input._flatpickr) {
    if (normalized === '') {
      input._flatpickr.clear();
      return;
    }
    input._flatpickr.setDate(normalized, true, 'Y-m-d H:i:S');
    return;
  }
  if (input) {
    input.value = normalized;
  }
}

function isTimeValueTypeInput(input) {
  return input && input.dataset && input.dataset.valueType === '6';
}

function initDateTimePickers() {
  if (typeof window.flatpickr !== 'function') {
    return;
  }
  document.querySelectorAll('input.field-datetime[data-value-type="6"]').forEach((input) => {
    if (input._flatpickr) {
      return;
    }
    window.flatpickr(input, {
      enableTime: true,
      allowInput: true,
      enableSeconds: true,
      time_24hr: true,
      altInput: true,
      dateFormat: 'Y-m-d H:i:S',
      altFormat: input.dataset.altFormat || 'F j, Y  H:i:S',
      locale: input.dataset.locale || 'default',
    });
  });
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
    const placeholder = escapeHtmlAttribute(getArrayInputPlaceholder(i18n, valueType, isExisting));
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

  const placeholder = escapeHtmlAttribute(getArrayInputPlaceholder(i18n, valueType, isExisting));
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

function buildArrayCurrentValueLabel(editor, rowModel) {
  const isExisting = rowModel.isExisting === true;
  const isDeleted = rowModel.isDeleted === true;
  const originalValue = rowModel.originalValue || '';
  if (!isExisting) {
    return `
      <strong class="config-current-value text-muted fst-italic mb-0">(new item)</strong>
    `;
  }
  if (isDeleted) {
    const normalizedDeleted = normalizeArrayEditorItem(originalValue);
    if (normalizedDeleted === '') {
      return `
        <strong class="config-current-value text-muted fst-italic mb-0">(not set)</strong>
      `;
    }
    return `
      <strong class="config-current-value text-danger mb-0">${escapeHtmlAttribute(normalizedDeleted)}</strong>
    `;
  }
  const normalized = normalizeArrayEditorItem(originalValue);
  if (normalized === '') {
    return `
      <strong class="config-current-value text-muted fst-italic mb-0">(not set)</strong>
    `;
  }
  const defaultItem = resolveArrayDefaultItem(editor);
  const valueClass = normalized === defaultItem ? 'text-success' : 'text-primary';
  return `
    <strong class="config-current-value ${valueClass} mb-0">${escapeHtmlAttribute(normalized)}</strong>
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
      <div class="array-row-current" data-array-current-cell>
        ${buildArrayCurrentValueLabel(editor, rowModel)}
      </div>
      <div class="array-row-editor">
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

function setArrayRowDeleteState(editor, row, isDeleted) {
  row.dataset.arrayRowDeleted = isDeleted ? '1' : '0';
  const deleteButton = row.querySelector('[data-array-remove-row]');
  setArrayDeleteButtonState(deleteButton, isDeleted);
  const currentCell = row.querySelector('[data-array-current-cell]');
  if (!currentCell) {
    return;
  }
  currentCell.innerHTML = buildArrayCurrentValueLabel(editor, getArrayRowMeta(row));
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
      if (!rowsContainer) {
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
      if (!rowsContainer || !row) {
        return;
      }
      const meta = getArrayRowMeta(row);
      if (!meta.isExisting) {
        row.remove();
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

function ensureConfigChangeConfirmModal(i18n) {
  let modalRoot = document.getElementById('system-settings-change-confirm-modal');
  if (!modalRoot) {
    modalRoot = document.createElement('div');
    modalRoot.id = 'system-settings-change-confirm-modal';
    modalRoot.className = 'modal fade';
    modalRoot.tabIndex = -1;
    modalRoot.setAttribute('aria-labelledby', 'system-settings-change-confirm-title');
    modalRoot.setAttribute('aria-hidden', 'true');
    modalRoot.innerHTML = `
      <div class="modal-dialog modal-xl modal-dialog-scrollable">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title" id="system-settings-change-confirm-title">${escapeHtmlAttribute(
              t(i18n, 'changeConfirmTitle', 'You are about to modify the following configuration(s):')
            )}</h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
          </div>
          <div class="modal-body">
            <p class="text-muted mb-3">${escapeHtmlAttribute(
              t(i18n, 'changeConfirmQuestion', 'Are you sure you want to save these changes?')
            )}</p>
            <div class="table-responsive">
              <table class="table table-sm table-bordered align-middle mb-0">
                <thead class="table-light">
                  <tr>
                    <th style="width: 26%">${escapeHtmlAttribute(t(i18n, 'confirmField', 'Field'))}</th>
                    <th style="width: 37%">${escapeHtmlAttribute(t(i18n, 'confirmFrom', 'Current'))}</th>
                    <th style="width: 37%">${escapeHtmlAttribute(t(i18n, 'confirmTo', 'New Value'))}</th>
                  </tr>
                </thead>
                <tbody data-change-rows></tbody>
              </table>
            </div>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">${escapeHtmlAttribute(
              t(i18n, 'cancel', 'Cancel')
            )}</button>
            <button type="button" class="btn btn-primary" data-confirm-submit="true">${escapeHtmlAttribute(
              t(i18n, 'confirmSave', 'Confirm Save')
            )}</button>
          </div>
        </div>
      </div>
    `;
    document.body.appendChild(modalRoot);
  }

  const bootstrapApi = window.bootstrap;
  if (!bootstrapApi || typeof bootstrapApi.Modal !== 'function') {
    return null;
  }

  const modalInstance = bootstrapApi.Modal.getOrCreateInstance(modalRoot, {
    backdrop: 'static',
    keyboard: false,
  });
  const rowsContainer = modalRoot.querySelector('[data-change-rows]');
  const confirmButton = modalRoot.querySelector('[data-confirm-submit="true"]');
  if (!rowsContainer || !confirmButton) {
    return null;
  }

  return {
    modalInstance,
    rowsContainer,
    confirmButton,
  };
}

function normalizeFieldLabelFromConfigKey(key) {
  return key.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function normalizeChangesForSubmit() {
  const changes = [];
  document.querySelectorAll('[name^="config_modify_"]').forEach((input) => {
    const rawValue = input.value ? input.value.trim() : '';
    const value = isTimeValueTypeInput(input) ? pickerDateTimeToIso(input, rawValue) : rawValue;
    if (isTimeValueTypeInput(input) && value !== '') {
      input.value = value;
    }
    const key = input.name.replace('config_modify_', '');
    const currentValueEl = document.querySelector(`[data-current-${key}]`);
    let currentValue = currentValueEl ? currentValueEl.textContent.trim() : '';
    if (!currentValue) {
      const arrayCurrentScript = document.getElementById(`array_current_value_${key}`);
      if (arrayCurrentScript) {
        const parsedCurrentValue = parseConfigPayload((arrayCurrentScript.textContent || '').trim());
        currentValue = Array.isArray(parsedCurrentValue)
          ? parsedCurrentValue.map((item) => normalizeArrayEditorItem(item)).join(', ')
          : normalizeCurrentConfigValue(parsedCurrentValue);
      }
    }
    if (value) {
      changes.push({
        key: normalizeFieldLabelFromConfigKey(key),
        from: currentValue,
        to: value,
      });
      return;
    }
    const clearFlag = document.getElementById(`config_clear_${key}`);
    if (clearFlag && clearFlag.value === '1') {
      changes.push({
        key: normalizeFieldLabelFromConfigKey(key),
        from: currentValue,
        to: '<cleared>',
      });
    }
  });
  return changes;
}

function setupConfigChangeConfirmation(i18n) {
  const form = document.getElementById('config-settings-form');
  if (!form) {
    return;
  }

  const modalHandle = ensureConfigChangeConfirmModal(i18n);
  let allowDirectSubmit = false;

  form.addEventListener('submit', (event) => {
    if (allowDirectSubmit) {
      return;
    }
    const changes = normalizeChangesForSubmit();
    if (changes.length === 0) {
      event.preventDefault();
      window.alert(t(i18n, 'noChanges', 'No changes to save. All modification fields are empty.'));
      return;
    }

    if (modalHandle === null) {
      event.preventDefault();
      window.alert(
        t(i18n, 'confirmModalUnavailable', 'Confirmation dialog is unavailable. Please refresh the page and try again.')
      );
      return;
    }

    event.preventDefault();
    modalHandle.rowsContainer.innerHTML = changes
      .map(
        (change) => `
          <tr>
            <td><code>${escapeHtmlAttribute(change.key)}</code></td>
            <td><span class="text-muted">${escapeHtmlAttribute(change.from || '(empty)')}</span></td>
            <td><strong>${escapeHtmlAttribute(change.to || '(empty)')}</strong></td>
          </tr>
        `
      )
      .join('');
    modalHandle.modalInstance.show();
  });

  if (modalHandle !== null) {
    modalHandle.confirmButton.addEventListener('click', () => {
      allowDirectSubmit = true;
      modalHandle.modalInstance.hide();
      if (typeof form.requestSubmit === 'function') {
        form.requestSubmit();
      } else {
        form.submit();
      }
    });
  }
}

function focusFirstFieldError() {
  const firstErrorRow = document.querySelector('.config-row.border-danger');
  if (!(firstErrorRow instanceof HTMLElement)) {
    return;
  }
  firstErrorRow.scrollIntoView({
    behavior: 'smooth',
    block: 'center',
    inline: 'nearest',
  });
  const focusTarget = firstErrorRow.querySelector('input, select, textarea, button');
  if (focusTarget instanceof HTMLElement) {
    window.setTimeout(() => {
      focusTarget.focus();
    }, 250);
  }
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
      const finalValue = isTimeValueTypeInput(input) ? isoToPickerDateTimeValue(normalizedValue) : normalizedValue;
      if (input.tagName === 'SELECT') {
        const hasOption = Array.from(input.options).some((option) => option.value === finalValue);
        if (!hasOption && finalValue !== '') {
          window.alert(t(i18n, 'currentValueNotSelectable', 'Current value is not available in selectable options.'));
          return;
        }
      }
      if (isTimeValueTypeInput(input)) {
        setPickerInputValue(input, normalizedValue);
      } else {
        input.value = finalValue;
      }
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
      const normalizedValue = normalizeCurrentConfigValue(parseConfigPayload(rawValue));
      if (isTimeValueTypeInput(input)) {
        setPickerInputValue(input, normalizedValue);
      } else {
        input.value = normalizedValue;
      }
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

export function initSystemSettingsPage(config = {}) {
  const i18n = config.i18n || {};

  initDateTimePickers();
  setupConfigChangeConfirmation(i18n);
  setupQuickNav();
  setupScalarInputs(i18n);
  document.querySelectorAll('[data-array-editor="true"]').forEach((editor) => {
    setupArrayEditor(editor, i18n);
  });
  focusFirstFieldError();
}
