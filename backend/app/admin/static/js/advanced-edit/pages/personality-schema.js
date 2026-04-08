export const personalitySchemaMethods = {
  renderSchemaFieldsTable() {
    const container = document.getElementById('schema-fields-table');
    const rows = [];
    this.state.fieldEntries.forEach((field) => {
      const requiredIcon = field.required ? '<i class="fas fa-check text-success"></i>' : '-';
      const description = field.description || field.default_description || '-';
      const fieldKey = encodeURIComponent(field.key || field.name || '');
      let categoryBadge = '<span class="badge text-bg-secondary">自定义</span>';
      if (field.group === 'system_fixed') {
        categoryBadge = '<span class="badge text-bg-primary">系统</span>';
      } else if (field.group === 'score_root') {
        categoryBadge = '<span class="badge text-bg-success">分数</span>';
      } else if (field.group === 'score_dimension') {
        categoryBadge = '<span class="badge text-bg-success">分数维度</span>';
      } else if (field.group === 'system_preset') {
        categoryBadge = '<span class="badge text-bg-info">预设</span>';
      }
      const displayFieldName = field.group === 'score_dimension' ? `score.${field.name}` : field.name;

      let actions = `<button class="btn btn-outline-primary" onclick="app.showSchemaFieldModal('${fieldKey}')"><i class="fas fa-edit"></i></button>`;
      if (field.deletable) {
        actions += ` <button class="btn btn-danger" onclick="app.deleteSchemaField('${fieldKey}')"><i class="fas fa-trash"></i></button>`;
      }

      rows.push(`<tr>
        <td>${categoryBadge}</td>
        <td><code>${this.escapeHtml(displayFieldName || '-')}</code></td>
        <td>${this.escapeHtml(field.type || '-')}</td>
        <td>${this.escapeHtml(description)}</td>
        <td>${requiredIcon}</td>
        <td>${actions}</td>
      </tr>`);
    });

    container.innerHTML = `<div class="table-responsive"><table class="table align-middle">
      <thead><tr><th>Category</th><th>Field</th><th>Type</th><th>Description</th><th>Required</th><th>Actions</th></tr></thead>
      <tbody>${rows.join('')}</tbody>
    </table></div>`;
  },

  showSchemaFieldModal(fieldKey = null) {
    const normalizedFieldKey = fieldKey ? decodeURIComponent(fieldKey) : '';
    const nameInput = document.getElementById('modal-field-name');
    const nameRequiredMark = document.getElementById('modal-field-name-required-mark');
    const typeRequiredMark = document.getElementById('modal-field-type-required-mark');
    const typeSelect = document.getElementById('modal-field-type');
    const typeRow = document.getElementById('modal-field-type-row');
    const descInput = document.getElementById('modal-field-description');
    const defaultDescInput = document.getElementById('modal-field-default-description');
    const restoreDefaultBtn = document.getElementById('modal-field-restore-default');
    const requiredCheck = document.getElementById('modal-field-required');
    const requiredRow = document.getElementById('modal-field-required-row');
    const modeInput = document.getElementById('modal-field-mode');
    const keyInput = document.getElementById('modal-field-key');
    const modalTitle = document.getElementById('schema-modal-title');

    if (!normalizedFieldKey) {
      keyInput.value = '';
      modeInput.value = 'create_custom';
      modalTitle.textContent = '添加自定义字段';
      nameInput.value = '';
      nameInput.readOnly = false;
      nameInput.disabled = false;
      typeSelect.value = 'string';
      typeSelect.disabled = false;
      typeRow.classList.remove('d-none');
      requiredRow.classList.remove('d-none');
      requiredCheck.checked = false;
      requiredCheck.disabled = false;
      nameRequiredMark.classList.remove('d-none');
      typeRequiredMark.classList.remove('d-none');
      descInput.value = '';
      descInput.readOnly = false;
      descInput.disabled = false;
      defaultDescInput.textContent = '-';
      restoreDefaultBtn.classList.add('d-none');
      this.state.schemaFieldModal.show();
      return;
    }

    const field = this.findFieldEntryByKey(normalizedFieldKey);
    if (!field) {
      return;
    }
    keyInput.value = field.key || field.name;
    modeInput.value = field.group || 'custom';
    modalTitle.textContent = '编辑字段';
    nameInput.value = field.name || '';
    nameInput.readOnly = !!field.locked_name;
    nameInput.disabled = !!field.locked_name;
    typeSelect.value = field.type || 'string';
    typeSelect.disabled = !!field.locked_type;
    requiredCheck.checked = !!field.required;
    requiredCheck.disabled = !!field.locked_required;
    descInput.value = field.description || '';
    descInput.readOnly = !field.editable_description;
    descInput.disabled = !field.editable_description;
    defaultDescInput.textContent = field.default_description || '-';
    restoreDefaultBtn.classList.toggle('d-none', !(field.restorable && field.default_description));
    const showTypeAndRequired = field.group === 'custom' || field.group === 'system_preset';
    typeRow.classList.toggle('d-none', !showTypeAndRequired);
    requiredRow.classList.toggle('d-none', !showTypeAndRequired);
    nameRequiredMark.classList.add('d-none');
    typeRequiredMark.classList.add('d-none');
    this.state.schemaFieldModal.show();
  },

  restoreSchemaFieldDefaultDescription() {
    const fieldKey = document.getElementById('modal-field-key').value;
    if (fieldKey === '') {
      return;
    }
    const field = this.findFieldEntryByKey(fieldKey);
    if (!field || !field.restorable) {
      return;
    }
    document.getElementById('modal-field-description').value = field.default_description || '';
  },

  saveSchemaField() {
    const fieldKey = document.getElementById('modal-field-key').value;
    const mode = document.getElementById('modal-field-mode').value;
    const name = document.getElementById('modal-field-name').value.trim();
    const type = document.getElementById('modal-field-type').value;
    const description = document.getElementById('modal-field-description').value.trim();
    const required = document.getElementById('modal-field-required').checked;

    if (!name) {
      alert('Field Name不能为空');
      return;
    }

    const isCreate = mode === 'create_custom';
    const existing = isCreate ? null : this.findFieldEntryByKey(fieldKey);
    if (!isCreate && !existing) {
      return;
    }

    const reserved = new Set([
      'should_block',
      'should_reply',
      'attack_detected',
      'should_update_memory',
      'memory_operations',
      'followup_messages',
      'outgoing_messages',
      'score',
    ]);
    const shouldValidateName = isCreate || (existing && !existing.locked_name);
    if (shouldValidateName) {
      const existingConflict = this.state.fieldEntries.find((item) => {
        if ((item.key || item.name) === fieldKey) {
          return false;
        }
        return item.name === name;
      });
      if (existingConflict) {
        alert('字段名重复');
        return;
      }
      if (reserved.has(name)) {
        alert('字段名与系统字段冲突');
        return;
      }
    }

    const shouldValidateType = isCreate || (existing && !existing.locked_type);
    if (shouldValidateType && (name === 'current_state' || name === 'internal_thoughts') && type !== 'string') {
      alert(`${name} 必须使用 string 类型`);
      return;
    }

    if (isCreate) {
      this.state.fieldEntries.push({
        key: name,
        name,
        group: 'custom',
        type,
        required,
        description,
        default_description: '',
        editable_description: true,
        restorable: false,
        deletable: true,
        locked_name: false,
        locked_type: false,
        locked_required: false,
        min: null,
        max: null,
        is_default: !description,
        exists: true,
      });
    } else {
      existing.name = existing.locked_name ? existing.name : name;
      existing.key = existing.locked_name ? existing.key : name;
      existing.type = existing.locked_type ? existing.type : type;
      existing.required = existing.locked_required ? existing.required : required;
      existing.description = existing.editable_description ? description : existing.description;
      existing.is_default = (existing.description || '') === (existing.default_description || '');
    }

    this.renderSchemaFieldsTable();
    this.state.schemaFieldModal.hide();
  },

  deleteSchemaField(fieldKey) {
    const normalizedFieldKey = decodeURIComponent(fieldKey || '');
    const fieldIndex = this.state.fieldEntries.findIndex((entry) => entry.key === normalizedFieldKey);
    if (fieldIndex < 0) {
      return;
    }
    const field = this.state.fieldEntries[fieldIndex];
    if (!field.deletable) {
      return;
    }
    void (async () => {
      const ok = await this.confirmAction({
        title: '确认删除字段',
        message: '确认删除此自定义字段吗？',
        confirmText: '删除',
        cancelText: '取消',
        confirmButtonClass: 'btn btn-danger',
      });
      if (!ok) return;
      this.state.fieldEntries.splice(fieldIndex, 1);
      this.renderSchemaFieldsTable();
    })();
  },

  showPresetFieldModal() {
    // Get available preset fields (not already added)
    const existingFieldNames = new Set(this.getEditableCustomEntries().map((field) => field.name));
    const availablePresets = this.state.availablePresets.filter((preset) => !existingFieldNames.has(preset.name));

    if (availablePresets.length === 0) {
      alert('所有预设字段已添加');
      return;
    }

    // Render available presets
    const container = document.getElementById('preset-fields-list');
    container.innerHTML = availablePresets
      .map(
        (p, idx) => `
      <div class="form-check">
        <input class="form-check-input" type="checkbox" value="${idx}" id="preset-${idx}">
        <label class="form-check-label" for="preset-${idx}">
          <strong>${p.name}</strong> (${p.type}) - ${p.description}
        </label>
      </div>
    `
      )
      .join('');

    // Store available presets for later use
    this.state.presetCandidates = availablePresets;
    this.state.presetFieldModal.show();
  },

  addPresetFields() {
    const checkboxes = document.querySelectorAll('#preset-fields-list input[type="checkbox"]:checked');
    if (checkboxes.length === 0) {
      alert('请至少选择一个字段');
      return;
    }

    checkboxes.forEach((cb) => {
      const idx = parseInt(cb.value);
      const preset = this.state.presetCandidates[idx];
      if (!preset) {
        return;
      }
      this.state.fieldEntries.push({
        key: preset.key || preset.name,
        name: preset.name,
        group: 'system_preset',
        type: preset.type,
        description: preset.description || '',
        required: !!preset.required,
        default_description: preset.default_description || '',
        editable_description: preset.editable_description !== false,
        restorable: preset.restorable !== false,
        deletable: true,
        locked_name: preset.locked_name !== false,
        locked_type: preset.locked_type !== false,
        locked_required: preset.locked_required !== false,
        min: null,
        max: null,
        is_default: true,
        exists: true,
      });
    });

    this.renderSchemaFieldsTable();
    this.state.presetFieldModal.hide();
  },
};
