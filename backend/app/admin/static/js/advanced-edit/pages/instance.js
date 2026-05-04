import {
  V1_ALGORITHM,
  bindAlgorithmParamsVisibility,
  collectAlgorithmParams,
  getSpecsForAlgorithm,
} from '../common/algorithm-params.js';
import { createMemoryController } from '../common/memory-controller.js';
import { createSnapshotGuard } from '../common/edit-guard.js';
import { postJson, withButtonLoading } from '../common/save-flow.js';

const config = window.ailoAdvancedEditInstanceConfig || {};
const dialogs = window.ailoDialogs;

function requireNumericId(value, name) {
  const strValue = typeof value === 'string' ? value : String(value ?? '');
  if (!/^\d+$/.test(strValue)) {
    throw new Error(`Invalid ${name} for AI instance advanced edit page`);
  }
  return strValue;
}

const instanceId = requireNumericId(config.instanceId, 'instanceId');

function confirmAction(options) {
  return dialogs.confirm(options);
}

function buildInstancePayload(formElement) {
  const formData = new FormData(formElement);

  const variables = {};
  for (const [key, value] of formData.entries()) {
    if (key.startsWith('var_') && value) {
      variables[key.substring(4)] = value;
    }
  }

  const dimensions = [];
  const missingParamMessages = [];
  document.querySelectorAll('.dimension-section').forEach((section) => {
    const dimensionId = section.dataset.dimensionId;
    const dimensionDisplay = section.dataset.dimensionDisplay || `Dimension ${dimensionId}`;
    const algStr = (formData.get(`algorithm_${dimensionId}`) || '').toString().trim();
    const scoreStr = (formData.get(`score_${dimensionId}`) || '').toString().trim();

    if (!algStr || !scoreStr) {
      return;
    }

    const algorithm = parseInt(algStr, 10);
    const score = parseInt(scoreStr, 10);
    if (Number.isNaN(algorithm) || Number.isNaN(score)) {
      return;
    }

    const dimData = {
      dimension_id: parseInt(dimensionId, 10),
      score,
      position_mapping_algorithm: algorithm,
    };

    if (algorithm === V1_ALGORITHM) {
      const specs = getSpecsForAlgorithm(config.algorithmParamSpecs, algorithm);
      const { params, missing } = collectAlgorithmParams(specs, dimensionId, formData);
      if (missing.length) {
        missingParamMessages.push(`${dimensionDisplay}: ${missing.join(', ')}`);
        return;
      }
      dimData.position_mapping_params = params;
    }

    dimensions.push(dimData);
  });

  const positions = {};
  document.querySelectorAll('.dimension-section').forEach((section) => {
    const dimensionId = section.dataset.dimensionId;
    const posInput = section.querySelector(`input[name="position_${dimensionId}"]`);
    if (posInput && posInput.value !== '') {
      positions[dimensionId] = parseInt(posInput.value, 10);
    }
  });

  const relationshipIdInput = document.getElementById('selected-relationship-id');
  const relationshipId =
    relationshipIdInput && relationshipIdInput.value ? parseInt(relationshipIdInput.value, 10) : null;

  return {
    payload: {
      prompt_variables: variables,
      dimensions,
      positions,
      relationship_id: relationshipId,
    },
    missingParamMessages,
  };
}

function buildOverridesFromForm() {
  const form = document.getElementById('main-form');
  const fd = new FormData(form);
  const overrides = { dimensions: [] };
  const missingParams = [];
  document.querySelectorAll('.dimension-section').forEach((section) => {
    const dimensionId = section.dataset.dimensionId;
    const dimensionDisplay = section.dataset.dimensionDisplay || `Dimension ${dimensionId}`;
    const algStr = (fd.get(`algorithm_${dimensionId}`) || '').toString().trim();
    const scoreStr = (fd.get(`score_${dimensionId}`) || '').toString().trim();
    if (!algStr || !scoreStr) {
      return;
    }
    const algorithm = parseInt(algStr, 10);
    const score = parseInt(scoreStr, 10);
    if (Number.isNaN(algorithm) || Number.isNaN(score)) {
      return;
    }
    const obj = {
      dimension_id: parseInt(dimensionId, 10),
      score,
      position_mapping_algorithm: algorithm,
    };
    if (algorithm === V1_ALGORITHM) {
      const specs = getSpecsForAlgorithm(config.algorithmParamSpecs, algorithm);
      const { params, missing } = collectAlgorithmParams(specs, dimensionId, fd);
      if (missing.length) {
        missingParams.push(`${dimensionDisplay}: ${missing.join(', ')}`);
        return;
      }
      obj.position_mapping_params = params;
    }
    overrides.dimensions.push(obj);
  });
  return { overrides, missingParams };
}

function bindAlgorithmVisibility() {
  bindAlgorithmParamsVisibility({
    selectSelector: '.algorithm-select',
    resolveParamsContainer: (select) =>
      document.querySelector(`.algorithm-params[data-dimension-id="${select.dataset.dimensionId}"]`),
    isActiveAlgorithm: (value) => String(value) === String(V1_ALGORITHM),
  });
}

function bindCancel(snapshotGuard) {
  document.getElementById('btn-cancel-instance-edit')?.addEventListener('click', async (event) => {
    event.preventDefault();
    const ok = await confirmAction({
      title: '确认返回列表',
      message: '确认放弃当前编辑并返回 AI Instances 列表页吗？<br>未保存的修改将会丢失。',
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
    const { payload, missingParamMessages } = buildInstancePayload(event.target);
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
          ? '确认保存当前实例编辑内容，并返回 AI Instances 列表页吗？'
          : '确认保存当前实例编辑内容，并继续留在本页面吗？',
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
          const result = await postJson(`/admin-api/ai/ai_instance/${instanceId}/save`, 'POST', payload);
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

function applyGeneratedResult(result) {
  if (result.dimension_results) {
    result.dimension_results.forEach((dimensionResult) => {
      const section = document.querySelector(`.dimension-section[data-dimension-id="${dimensionResult.dimension_id}"]`);
      if (!section) {
        return;
      }
      const posDisplay = section.querySelector('.position-display');
      const hidden = section.querySelector(`input[name="position_${dimensionResult.dimension_id}"]`);
      if (posDisplay) {
        posDisplay.textContent = dimensionResult.final_position;
      }
      if (hidden) {
        hidden.value = dimensionResult.final_position;
      }
    });
  }

  const rel = result.selected_relationship;
  const relDisplay = document.getElementById('current-relationship-display');
  const relInput = document.getElementById('selected-relationship-id');
  if (rel) {
    const relName = rel.relationship_display_name || `ID ${rel.relationship_id || 'Unknown'}`;
    if (relDisplay) {
      relDisplay.textContent = relName;
    }
    if (relInput) {
      relInput.value = rel.relationship_id;
    }
    alert(`Generated successfully!\nRelationship: ${relName}\nPlease click Save to persist changes.`);
  } else {
    if (relDisplay) {
      relDisplay.textContent = 'Not set';
    }
    if (relInput) {
      relInput.value = '';
    }
    alert('Generated successfully!\nNo relationship selected.\nPlease click Save to persist changes.');
  }
}

function bindGenerateRelationship() {
  document.getElementById('generate-relationship-btn')?.addEventListener('click', async () => {
    const btn = document.getElementById('generate-relationship-btn');
    const confirmed = await confirmAction({
      title: '确认生成关系',
      message: '确认使用当前表单值生成 relationship 预览吗？<br>生成结果会回填到表单，保存后才会真正持久化。',
      confirmText: '生成预览',
      cancelText: '取消',
      confirmButtonClass: 'btn btn-primary',
    });
    if (!confirmed) {
      return;
    }

    await withButtonLoading(
      btn,
      '<span class="spinner-border spinner-border-sm me-2"></span>Generating...',
      async () => {
        try {
          const { overrides, missingParams } = buildOverridesFromForm();
          if (missingParams.length) {
            alert(`请先填写所有算法参数：\n${missingParams.join('\n')}`);
            return;
          }

          const result = await postJson(`/admin-api/ai/ai_instance/${instanceId}/generate-relationship`, 'POST', {
            overrides,
            preview: true,
          });
          if (result.ok) {
            applyGeneratedResult(result.data || {});
            return;
          }
          alert(`Generation failed: ${(result.data && result.data.detail) || 'Unknown error'}`);
        } catch (error) {
          alert(`Generation failed: ${error.message}`);
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
    document.getElementById('memory-status').value = memory.status;
    document.getElementById('memory-source-msg').value = memory.source_message_id || '';
    document.getElementById('memory-content').value = memory.content;
  },
  onCreateFormReady: () => {
    document.getElementById('memory-id').value = '';
  },
  buildSaveRequest: ({ formData, isEdit, memoryId }) => {
    const payload = {
      instance_id: instanceId,
      memory_type: formData.get('memory_type'),
      importance: parseInt(formData.get('importance'), 10),
      status: parseInt(formData.get('status'), 10),
      content: formData.get('content'),
    };
    const sourceMsgId = formData.get('source_message_id');
    if (sourceMsgId) {
      payload.source_message_id = String(sourceMsgId).trim();
    }
    return {
      url: isEdit ? `/admin-api/ai/instance-memory/${memoryId}/update` : '/admin-api/ai/instance-memory/create',
      method: isEdit ? 'PUT' : 'POST',
      payload,
    };
  },
  buildDeleteRequest: (memoryId) => ({
    url: `/admin-api/ai/instance-memory/${memoryId}/delete`,
    method: 'DELETE',
  }),
  deleteConfirm: {
    title: '确认删除记忆',
    message: '确定删除这条实例记忆吗？此操作不可恢复。',
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
    buildPayload: () => buildInstancePayload(mainForm).payload,
  });
  bindCancel(snapshotGuard);
  bindSubmit(mainForm, snapshotGuard);
  bindGenerateRelationship();
  memoryController.init();
  memoryController.exposeGlobals();
}

init();
