import { createSnapshotGuard } from '../common/edit-guard.js';
import { postJson, withButtonLoading } from '../common/save-flow.js';
import { personalityStyleMethods } from './personality-style.js';
import { personalityPlaceholderMethods } from './personality-placeholders.js';
import { personalityCsvMethods } from './personality-csv.js';
import { personalitySchemaMethods } from './personality-schema.js';

const config = window.ailoAdvancedEditPersonalityConfig || {};

function requireNumericId(value, name) {
  const strValue = typeof value === 'string' ? value : String(value ?? '');
  if (!/^\d+$/.test(strValue)) {
    throw new Error(`Invalid ${name} for AI personality advanced edit page`);
  }
  return strValue;
}

const PERSONALITY_ID = requireNumericId(config.personalityId, 'personalityId');
const LIST_URL = config.listUrl;
const dialogs = window.ailoDialogs;

const app = {
  state: {
    placeholders: [],
    deletedPlaceholderIds: [],
    fieldEntries: [],
    styleSelectorModal: null,
    schemaFieldModal: null,
    presetFieldModal: null,
    availablePresets: [],
    constraints: {},
    presetCandidates: [],
    manualUndoOps: [],
    snapshotGuard: null,
    unsavedGuard: null,
    placeholderClientIdSeq: 0,
    placeholderCsvImportModal: null,
    placeholderCsvImportParsed: null,
    placeholderCsvImportSummary: null,
    // Cache for style -> dimensions to avoid repeated requests
    styleDimensionsCache: {},
    // Map of styleId -> <option> element for label updates
    styleOptionsMap: {},
    // Keep removed score-dimension drafts in current session only.
    orphanScoreDimensionDrafts: {},
  },

  buildPayload() {
    const scoreDimensions = this.getScoreDimensionEntries();
    const fixedFields = this.getFieldEntriesByGroup('system_fixed');
    const scoreRoot = this.getScoreRootEntry();
    const editableFields = this.state.fieldEntries.filter(
      (field) => field.group === 'system_preset' || field.group === 'custom'
    );
    return {
      prompt: (document.getElementById('prompt-editor')?.value || '').trim(),
      schema_config: {
        dimensions: scoreDimensions.map((dimension) => ({
          name: dimension.name,
          min: Number(dimension.min),
          max: Number(dimension.max),
          description: (dimension.description || '').trim(),
        })),
        standard_field_descriptions: fixedFields.map((field) => ({
          name: field.name,
          description: (field.description || '').trim(),
        })),
        score_description: (scoreRoot?.description || '').trim(),
        custom_fields: editableFields.map((field) => ({
          name: field.name,
          type: field.type,
          description: (field.description || '').trim(),
          required: !!field.required,
        })),
      },
      placeholders: this.state.placeholders.map((placeholder) => ({
        id: placeholder.id ?? null,
        placeholder_key: placeholder.placeholder_key ?? '',
        display_name: placeholder.display_name ?? '',
        description: placeholder.description ?? '',
        example_value: placeholder.example_value ?? '',
        is_required: !!placeholder.is_required,
      })),
      deleted_placeholder_ids: [...this.state.deletedPlaceholderIds],
    };
  },

  markSaved() {
    this.state.snapshotGuard?.markSaved(this.buildPayload());
  },

  async confirmAction(options) {
    return dialogs.confirm(options);
  },

  async init() {
    // Initialize modals
    this.state.styleSelectorModal = new bootstrap.Modal(document.getElementById('styleSelectorModal'));
    this.state.schemaFieldModal = new bootstrap.Modal(document.getElementById('schemaFieldModal'));
    this.state.presetFieldModal = new bootstrap.Modal(document.getElementById('presetFieldModal'));
    this.state.placeholderCsvImportModal = new bootstrap.Modal(document.getElementById('placeholderCsvImportModal'));

    // Bind style selector change to live preview
    const styleSelectorEl = document.getElementById('style-selector');
    if (styleSelectorEl) {
      styleSelectorEl.addEventListener('change', () => this.updateStylePreview());
    }

    // Load data
    await this.loadAdvancedConfig();
    await this.loadPlaceholders();
    await this.loadStyles();

    // Setup event listeners
    const editor = document.getElementById('prompt-editor');
    editor.addEventListener('input', () => this.validatePrompt());
    // Provide manual undo only for fallback insert operations
    editor.addEventListener('keydown', (e) => {
      const isUndo = (e.ctrlKey || e.metaKey) && (e.key === 'z' || e.key === 'Z');
      if (!isUndo) return;
      if (this.state.manualUndoOps.length === 0) return;
      e.preventDefault();
      const op = this.state.manualUndoOps.pop();
      const value = editor.value;
      if (value.slice(op.start, op.start + op.len) === op.text) {
        editor.setSelectionRange(op.start, op.start + op.len);
        document.execCommand('insertText', false, '');
        // If execCommand fails, fallback to manual remove
        if (editor.value === value) {
          editor.value = value.slice(0, op.start) + value.slice(op.start + op.len);
          editor.setSelectionRange(op.start, op.start);
        }
        this.validatePrompt();
      }
    });

    this.state.snapshotGuard = createSnapshotGuard({
      buildPayload: () => this.buildPayload(),
    });
    this.state.unsavedGuard = this.state.snapshotGuard.guard;

    // Initial render
    this.renderSystemPlaceholders();
    this.renderScorePlaceholders();
    this.renderCustomPlaceholders();
    this.renderPlaceholdersList();
    this.renderSchemaFieldsTable();
    this.validatePrompt();
    this.applyPlaceholderKeyValidationStyles();
    this.markSaved();

    this.bindPlaceholderListEvents();
    document.getElementById('btn-cancel-personality-edit')?.addEventListener('click', async (event) => {
      event.preventDefault();
      const ok = await this.confirmAction({
        title: '确认返回列表',
        message: '确认放弃当前编辑并返回 Personalities 列表页吗？<br>未保存的修改将会丢失。',
        confirmText: '放弃并返回',
        cancelText: '继续编辑',
        confirmButtonClass: 'btn btn-danger',
      });
      if (!ok) {
        return;
      }
      this.state.unsavedGuard?.bypassOnce();
      window.location.assign(LIST_URL);
    });
  },

  escapeHtml(value) {
    const str = value === null || value === undefined ? '' : String(value);
    return str
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#39;');
  },

  getFieldEntriesByGroup(groupName) {
    return this.state.fieldEntries.filter((entry) => entry.group === groupName);
  },

  getScoreRootEntry() {
    return this.state.fieldEntries.find((entry) => entry.group === 'score_root') || null;
  },

  getScoreDimensionEntries() {
    return this.getFieldEntriesByGroup('score_dimension');
  },

  getEditableCustomEntries() {
    return this.state.fieldEntries.filter((entry) => entry.group === 'custom' || entry.group === 'system_preset');
  },

  findFieldEntryByKey(fieldKey) {
    if (typeof fieldKey !== 'string' || fieldKey.trim() === '') {
      return null;
    }
    return this.state.fieldEntries.find((entry) => entry.key === fieldKey) || null;
  },

  validateDimensions() {
    const scoreDimensions = this.getScoreDimensionEntries();
    if (scoreDimensions.length === 0) {
      return '请先加载dimension信息';
    }
    for (let i = 0; i < scoreDimensions.length; i += 1) {
      const dim = scoreDimensions[i];
      if (!Number.isFinite(dim.min) || !Number.isFinite(dim.max)) {
        return `维度 ${dim.name} 的 min/max 必须是数字`;
      }
      if (Number(dim.min) >= Number(dim.max)) {
        return `维度 ${dim.name} 需要满足 min < max`;
      }
    }
    return null;
  },

  validateCustomFields() {
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
    const seen = new Set();
    const customFields = this.getEditableCustomEntries();
    for (let i = 0; i < customFields.length; i += 1) {
      const field = customFields[i];
      if (!field || typeof field.name !== 'string' || field.name.trim() === '') {
        return `第 ${i + 1} 个自定义字段名称不能为空`;
      }
      const name = field.name.trim();
      if (reserved.has(name)) {
        return `自定义字段 ${name} 与系统字段冲突`;
      }
      if (seen.has(name)) {
        return `自定义字段重复: ${name}`;
      }
      seen.add(name);
    }
    return null;
  },

  ...personalityStyleMethods,
  ...personalityPlaceholderMethods,
  ...personalityCsvMethods,
  ...personalitySchemaMethods,

  async save(action = 'save') {
    const payload = this.buildPayload();
    if (!payload.prompt) {
      alert('提示词不能为空');
      return;
    }

    const dimensionError = this.validateDimensions();
    if (dimensionError) {
      alert(dimensionError);
      return;
    }

    const customFieldError = this.validateCustomFields();
    if (customFieldError) {
      alert(customFieldError);
      return;
    }

    const placeholderErrors = this.validatePlaceholders();
    if (placeholderErrors.size > 0) {
      this.applyPlaceholderKeyValidationStyles();
      alert('Placeholder Key 存在错误：Key 必填、不可重复，且仅允许 [A-Za-z0-9_]+（禁止以 score: 开头）');
      return;
    }

    const confirmed = await this.confirmAction({
      title: action === 'save' ? '确认保存并返回' : '确认保存',
      message:
        action === 'save'
          ? '确认保存当前 Personality 编辑内容，并返回列表页吗？'
          : '确认保存当前 Personality 编辑内容，并继续留在本页面吗？',
      confirmText: action === 'save' ? '保存并返回' : '保存',
      cancelText: '取消',
      confirmButtonClass: 'btn btn-primary',
    });
    if (!confirmed) {
      return;
    }

    const submitBtn =
      action === 'save'
        ? document.getElementById('btn-save-personality-edit')
        : document.getElementById('btn-save-continue-personality-edit');

    try {
      await withButtonLoading(
        submitBtn,
        '<span class="spinner-border spinner-border-sm me-2"></span>Saving...',
        async () => {
          const result = await postJson(`/admin-api/ai/ai-personality/${PERSONALITY_ID}/save`, 'POST', payload);
          if (result.ok) {
            this.markSaved();
            this.state.unsavedGuard?.bypassOnce();
            if (action === 'save') {
              alert('保存成功');
              window.location.href = LIST_URL;
            } else {
              alert('保存成功');
              location.reload();
            }
            return;
          }
          alert('保存失败: ' + ((result.data && result.data.detail) || '未知错误'));
        }
      );
    } catch (error) {
      alert('保存失败: ' + error.message);
    }
  },
};

window.app = app;
document.addEventListener('DOMContentLoaded', () => app.init());
