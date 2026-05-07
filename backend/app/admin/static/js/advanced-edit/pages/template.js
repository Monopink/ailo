import {
  V1_ALGORITHM,
  bindAlgorithmParamsVisibility,
  collectAlgorithmParams,
  getSpecsForAlgorithm,
} from '../common/algorithm-params.js';
import { createMemoryController } from '../common/memory-controller.js';
import { createSnapshotGuard } from '../common/edit-guard.js';
import { postJson, withButtonLoading } from '../common/save-flow.js';

const config = window.ailoAdvancedEditTemplateConfig || {};
const dialogs = window.ailoDialogs;

function requireNumericId(value, name) {
  const strValue = typeof value === 'string' ? value : String(value ?? '');
  if (!/^\d+$/.test(strValue)) {
    throw new Error(`Invalid ${name} for AI template advanced edit page`);
  }
  return strValue;
}

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

const templateId = requireNumericId(config.templateId, 'templateId');

function confirmAction(options) {
  return dialogs.confirm(options);
}

function renderTemplateMemoryRow(memory) {
  const isPendingDelete = memory._archivedPending === true;
  const badgeClass = memory.memory_type === 'core' ? 'primary' : 'secondary';
  const deleteBtnClass = isPendingDelete ? 'btn-danger' : 'btn-outline-danger';
  const pendingHint = isPendingDelete
    ? '<div class="text-danger small mt-2"><i class="fas fa-trash me-1"></i>Pending delete (applies on Save)</div>'
    : '';

  return `
    <div class="list-group-item ${isPendingDelete ? 'border-danger' : ''}" data-memory-id="${escapeHtml(memory.id)}">
      <div class="d-flex justify-content-between align-items-start">
        <div class="flex-grow-1">
          <div class="d-flex align-items-center mb-2">
            <span class="badge bg-${badgeClass} me-2">${escapeHtml(memory.memory_type)}</span>
            <span class="badge bg-info me-2">Importance: ${escapeHtml(memory.importance)}</span>
            <span class="badge bg-light text-dark">Order: ${escapeHtml(memory.display_order)}</span>
          </div>
          <p class="mb-0">${escapeHtml(memory.content)}</p>
          ${pendingHint}
        </div>
        <div class="btn-group ms-3">
          <button
            type="button"
            class="btn btn-outline-primary"
            data-memory-action="edit"
            data-memory-id="${escapeHtml(memory.id)}"
          >
            <i class="fas fa-edit"></i> Edit
          </button>
          <button
            type="button"
            class="btn ${deleteBtnClass}"
            data-memory-action="toggle-archive"
            data-memory-id="${escapeHtml(memory.id)}"
            aria-pressed="${isPendingDelete ? 'true' : 'false'}"
          >
            <i class="fas fa-trash"></i> Delete
          </button>
        </div>
      </div>
    </div>
  `;
}

function buildTemplatePayload(formElement, memoryController) {
  const formData = new FormData(formElement);

  const variables = {};
  for (const [key, value] of formData.entries()) {
    if (key.startsWith('var_') && value) {
      variables[key.substring(4)] = value;
    }
  }

  const positionMappingConfig = {};
  const missingParamMessages = [];
  document.querySelectorAll('.dimension-config-section').forEach((section) => {
    const dimensionName = section.dataset.dimensionName;
    const dimensionDisplay = section.dataset.dimensionDisplay || dimensionName;
    const algorithm = parseInt(formData.get(`algorithm_${dimensionName}`), 10);

    positionMappingConfig[dimensionName] = { algorithm };

    if (algorithm === V1_ALGORITHM) {
      const specs = getSpecsForAlgorithm(config.algorithmParamSpecs, algorithm);
      const { params, missing } = collectAlgorithmParams(specs, dimensionName, formData);
      if (missing.length) {
        missingParamMessages.push(`${dimensionDisplay}: ${missing.join(', ')}`);
      } else {
        positionMappingConfig[dimensionName].params = params;
      }
    }
  });

  return {
    payload: {
      prompt_variables: variables,
      position_mapping_config: positionMappingConfig,
      memory_changes: memoryController.buildChanges(),
    },
    missingParamMessages,
  };
}

function bindAlgorithmVisibility() {
  bindAlgorithmParamsVisibility({
    selectSelector: '.algorithm-select',
    resolveParamsContainer: (select) =>
      document.querySelector(`.algorithm-params[data-dimension="${select.dataset.dimension}"]`),
    isActiveAlgorithm: (value) => String(value) === String(V1_ALGORITHM),
  });
}

function bindCancel(snapshotGuard) {
  document.getElementById('btn-cancel-template-edit')?.addEventListener('click', async (event) => {
    event.preventDefault();
    const ok = await confirmAction({
      title: '确认返回列表',
      message: '确认放弃当前编辑并返回 AI Templates 列表页吗？<br>未保存的修改将会丢失。',
      confirmText: '放弃并返回',
      cancelText: '继续编辑',
      confirmButtonClass: 'btn btn-danger',
    });
    if (!ok) {
      return;
    }
    snapshotGuard.guard.bypassOnce();
    window.location.assign(config.listUrl);
  });
}

function bindSubmit(mainForm, snapshotGuard, memoryController) {
  mainForm?.addEventListener('submit', async (event) => {
    event.preventDefault();
    const { payload, missingParamMessages } = buildTemplatePayload(event.target, memoryController);
    const action =
      event.submitter && event.submitter.dataset && event.submitter.dataset.action
        ? event.submitter.dataset.action
        : 'continue';

    if (missingParamMessages.length) {
      alert(`请完善以下算法参数：\n${missingParamMessages.join('\n')}`);
      return;
    }

    const confirmed = await confirmAction({
      title: action === 'save' ? '确认保存并返回' : '确认保存',
      message:
        action === 'save'
          ? '确认保存当前编辑内容，并返回 AI Templates 列表页吗？'
          : '确认保存当前编辑内容，并继续留在本页面吗？',
      confirmText: action === 'save' ? '保存并返回' : '保存',
      cancelText: '取消',
      confirmButtonClass: 'btn btn-primary',
    });
    if (!confirmed) {
      return;
    }

    const submitBtn = event.submitter || event.target.querySelector('button[type="submit"]');
    await withButtonLoading(
      submitBtn,
      '<span class="spinner-border spinner-border-sm me-2"></span>Saving...',
      async () => {
        try {
          const result = await postJson(`/admin-api/ai/ai_template/${templateId}/save`, 'POST', payload);
          if (result.ok) {
            snapshotGuard.markSaved(payload);
            snapshotGuard.guard.bypassOnce();
            if (action === 'save') {
              window.location.href = config.listUrl;
            } else {
              alert('Saved successfully');
              location.reload();
            }
            return;
          }
          alert(`Save failed: ${(result.data && result.data.detail) || 'Unknown error'}`);
        } catch (error) {
          alert(`Save failed: ${error.message}`);
        }
      }
    );
  });
}

function bindMemoryActions(memoryController) {
  document.getElementById('btn-open-memory-modal')?.addEventListener('click', () => {
    memoryController.openMemoryModal();
  });

  document.getElementById('btn-save-memory')?.addEventListener('click', () => {
    memoryController.saveMemory();
  });

  document.getElementById('memories-list')?.addEventListener('click', (event) => {
    const rawTarget = event.target;
    const targetElement =
      rawTarget && typeof rawTarget === 'object'
        ? rawTarget.nodeType === 1
          ? rawTarget
          : rawTarget.parentElement
        : null;
    const button = targetElement?.closest('button[data-memory-action][data-memory-id]');
    if (!button) {
      return;
    }
    const memoryId = button.dataset.memoryId;
    if (!memoryId) {
      return;
    }
    const action = button.dataset.memoryAction;
    if (action === 'edit') {
      memoryController.editMemory(memoryId);
      return;
    }
    if (action === 'toggle-archive') {
      memoryController.toggleArchive(memoryId);
    }
  });
}

const memoryController = createMemoryController({
  initialMemories: config.memories || [],
  comparableFields: ['memory_type', 'importance', 'display_order', 'content'],
  renderMemoryRow: renderTemplateMemoryRow,
  emptyListHtml:
    '<div class="alert alert-info"><i class="fas fa-info-circle me-2"></i>No memories defined for this template. Click "Add Memory" to create one.</div>',
  parseFormPayload: (formData) => ({
    memory_type: formData.get('memory_type'),
    importance: parseInt(formData.get('importance'), 10),
    display_order: parseInt(formData.get('display_order'), 10),
    content: (formData.get('content') || '').toString(),
  }),
  fillEditForm: (memory) => {
    document.getElementById('memory-id').value = memory.id;
    document.getElementById('memory-type').value = memory.memory_type;
    document.getElementById('memory-importance').value = memory.importance;
    document.getElementById('memory-order').value = memory.display_order;
    document.getElementById('memory-content').value = memory.content;
  },
  confirmRemoveNew: async (memory) => {
    if (!memory._isNew) {
      return true;
    }
    return confirmAction({
      title: '确认删除未保存记忆',
      message: '该记忆尚未保存到数据库，确认立即从当前页面移除吗？',
      confirmText: '删除',
      cancelText: '取消',
      confirmButtonClass: 'btn btn-danger',
    });
  },
});

function init() {
  const mainForm = document.getElementById('main-form');
  if (!mainForm) {
    return;
  }
  bindAlgorithmVisibility();
  memoryController.init();
  const snapshotGuard = createSnapshotGuard({
    buildPayload: () => buildTemplatePayload(mainForm, memoryController).payload,
  });
  bindCancel(snapshotGuard);
  bindSubmit(mainForm, snapshotGuard, memoryController);
  bindMemoryActions(memoryController);
}

init();
