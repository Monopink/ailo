import {
  V1_ALGORITHM,
  bindAlgorithmParamsVisibility,
  collectAlgorithmParams,
  getSpecsForAlgorithm,
} from '../common/algorithm-params.js';
import { createMemoryController } from '../common/memory-controller.js';
import { createSnapshotGuard } from '../common/edit-guard.js';
import { postJson, withButtonLoading } from '../common/save-flow.js';

const config = window.qiaoAdvancedEditTemplateConfig || {};
const dialogs = window.qiaoAdminDialogs;

function requireNumericId(value, name) {
  const strValue = typeof value === 'string' ? value : String(value ?? '');
  if (!/^\d+$/.test(strValue)) {
    throw new Error(`Invalid ${name} for AI template advanced edit page`);
  }
  return strValue;
}

const templateId = requireNumericId(config.templateId, 'templateId');

function confirmAction(options) {
  return dialogs.confirm(options);
}

function buildTemplatePayload(formElement) {
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

function bindSubmit(mainForm, snapshotGuard) {
  mainForm?.addEventListener('submit', async (event) => {
    event.preventDefault();
    const { payload, missingParamMessages } = buildTemplatePayload(event.target);
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

const memoriesData = config.memories || [];
const memoryController = createMemoryController({
  memoriesData,
  confirmAction,
  fillEditForm: (memory) => {
    document.getElementById('memory-id').value = memory.id;
    document.getElementById('memory-type').value = memory.memory_type;
    document.getElementById('memory-importance').value = memory.importance;
    document.getElementById('memory-order').value = memory.display_order;
    document.getElementById('memory-content').value = memory.content;
  },
  onCreateFormReady: () => {
    document.getElementById('memory-id').value = '';
  },
  buildSaveRequest: ({ formData, isEdit, memoryId }) => ({
    url: isEdit ? `/admin-api/ai/template-memory/${memoryId}/update` : '/admin-api/ai/template-memory/create',
    method: isEdit ? 'PUT' : 'POST',
    payload: {
      template_id: templateId,
      memory_type: formData.get('memory_type'),
      importance: parseInt(formData.get('importance'), 10),
      display_order: parseInt(formData.get('display_order'), 10),
      content: formData.get('content'),
    },
  }),
  buildDeleteRequest: (memoryId) => ({
    url: `/admin-api/ai/template-memory/${memoryId}/delete`,
    method: 'DELETE',
  }),
  deleteConfirm: {
    title: '确认删除记忆',
    message: '确定删除这条模板记忆吗？此操作不可恢复。',
    confirmText: '删除',
    cancelText: '取消',
    confirmButtonClass: 'btn btn-danger',
  },
});

function init() {
  const mainForm = document.getElementById('main-form');
  if (!mainForm) {
    return;
  }
  bindAlgorithmVisibility();
  const snapshotGuard = createSnapshotGuard({
    buildPayload: () => buildTemplatePayload(mainForm).payload,
  });
  bindCancel(snapshotGuard);
  bindSubmit(mainForm, snapshotGuard);
  memoryController.init();
  memoryController.exposeGlobals();
}

init();
