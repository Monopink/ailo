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

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

const instanceId = requireNumericId(config.instanceId, 'instanceId');

function confirmAction(options) {
  return dialogs.confirm(options);
}

function renderInstanceMemoryRow(memory, { canToggleArchive }) {
  const status = Number(memory.status || 1);
  const isNew = memory._isNew === true;
  const canArchive = canToggleArchive(memory);
  const isPendingArchive = memory._archivedPending === true;

  const typeBadgeClass = memory.memory_type === 'core' ? 'primary' : 'secondary';
  const statusBadgeClass = isPendingArchive ? 'danger' : status === 1 ? 'success' : 'warning';
  const statusText = isPendingArchive ? 'Pending Archive' : status === 1 ? 'Active' : 'Archived';

  const archiveBtnClass = isNew ? 'btn-outline-danger' : isPendingArchive ? 'btn-warning' : 'btn-outline-warning';
  const archiveBtnIcon = isNew ? 'fa-trash' : 'fa-archive';
  const archiveBtnText = isNew ? 'Delete' : 'Archive';
  const archiveDisabled = !canArchive ? 'disabled' : '';
  const editDisabled = status === 1 ? '' : 'disabled';
  const pendingHint = isPendingArchive
    ? '<div class="text-danger small mt-2"><i class="fas fa-archive me-1"></i>Pending archive (applies on Save)</div>'
    : '';

  return `
    <div class="list-group-item ${isPendingArchive ? 'border-danger' : ''}" data-memory-id="${escapeHtml(memory.id)}">
      <div class="d-flex justify-content-between align-items-start">
        <div class="flex-grow-1">
          <div class="d-flex align-items-center mb-2 flex-wrap gap-1">
            <span class="badge bg-${typeBadgeClass}">${escapeHtml(memory.memory_type)}</span>
            <span class="badge bg-info">Importance: ${escapeHtml(memory.importance)}</span>
            <span class="badge bg-dark">Source: S${escapeHtml(memory.source_strength)}</span>
            <span class="badge bg-secondary">Reinforce: ${escapeHtml(memory.reinforce_count)}</span>
            <span class="badge bg-${statusBadgeClass}">${statusText}</span>
            ${
              memory.fact_key
                ? `<span class="badge bg-light text-dark">Fact: ${escapeHtml(memory.fact_key)}</span>`
                : ''
            }
            ${memory.conflict_flag ? '<span class="badge bg-danger">Conflict Marked</span>' : ''}
            ${
              memory.expires_at
                ? `<span class="badge bg-light text-dark">Expires: <span class="datetime-display" data-datetime="${escapeHtml(
                    memory.expires_at
                  )}">${escapeHtml(memory.expires_at)}</span></span>`
                : ''
            }
          </div>
          <p class="mb-1">${escapeHtml(memory.content)}</p>
          <small class="text-muted">
            Created: <span class="datetime-display" data-datetime="${escapeHtml(memory.created_at || '')}">${escapeHtml(
              memory.created_at || 'N/A'
            )}</span>
            ${
              memory.last_reinforced_at
                ? ` | Last Reinforced: <span class="datetime-display" data-datetime="${escapeHtml(
                    memory.last_reinforced_at
                  )}">${escapeHtml(memory.last_reinforced_at)}</span>`
                : ''
            }
            ${
              memory.refreshed_at
                ? ` | Refreshed: <span class="datetime-display" data-datetime="${escapeHtml(
                    memory.refreshed_at
                  )}">${escapeHtml(memory.refreshed_at)}</span>`
                : ''
            }
            ${memory.source_message_id ? ` | Source MSG: ${escapeHtml(memory.source_message_id)}` : ''}
            ${
              memory.normalized_content
                ? ` | Normalized: ${escapeHtml(memory.normalized_content.slice(0, 80))}${
                    memory.normalized_content.length > 80 ? '...' : ''
                  }`
                : ''
            }
          </small>
          ${pendingHint}
        </div>
        <div class="btn-group ms-3">
          <button
            type="button"
            class="btn btn-outline-primary"
            data-memory-action="edit"
            data-memory-id="${escapeHtml(memory.id)}"
            ${editDisabled}
          >
            <i class="fas fa-edit"></i> Edit
          </button>
          <button
            type="button"
            class="btn ${archiveBtnClass}"
            data-memory-action="toggle-archive"
            data-memory-id="${escapeHtml(memory.id)}"
            aria-pressed="${isPendingArchive ? 'true' : 'false'}"
            ${archiveDisabled}
          >
            <i class="fas ${archiveBtnIcon}"></i> ${archiveBtnText}
          </button>
        </div>
      </div>
    </div>
  `;
}

function buildInstancePayload(formElement, memoryController) {
  const formData = new FormData(formElement);
  const rawStatus = (formData.get('status') || '').toString().trim();
  let parsedStatus = null;
  let statusError = null;
  if (rawStatus !== '') {
    const statusValue = parseInt(rawStatus, 10);
    if (Number.isNaN(statusValue)) {
      statusError = 'Status must be an integer';
    } else if (statusValue !== 1 && statusValue !== 2) {
      statusError = 'Status can only be Active or Inactive in advanced edit';
    } else {
      parsedStatus = statusValue;
    }
  }

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

  const payload = {
    prompt_variables: variables,
    dimensions,
    positions,
    relationship_id: relationshipId,
    memory_changes: memoryController.buildChanges(),
  };
  if (parsedStatus !== null) {
    payload.status = parsedStatus;
  }

  return { payload, missingParamMessages, statusError };
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

function bindSubmit(mainForm, snapshotGuard, memoryController) {
  mainForm?.addEventListener('submit', async (event) => {
    event.preventDefault();
    const { payload, missingParamMessages, statusError } = buildInstancePayload(event.target, memoryController);
    const action =
      event.submitter && event.submitter.dataset && event.submitter.dataset.action
        ? event.submitter.dataset.action
        : 'continue';

    if (missingParamMessages.length) {
      alert(`请完善以下算法参数：\n${missingParamMessages.join('\n')}`);
      return;
    }
    if (statusError) {
      alert(statusError);
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

function bindPreviewPanelClose() {
  document.getElementById('btn-close-gen-preview')?.addEventListener('click', () => {
    const panel = document.getElementById('genPreviewPanel');
    if (panel) {
      panel.style.display = 'none';
    }
  });
}

const memoryController = createMemoryController({
  initialMemories: config.memories || [],
  comparableFields: ['memory_type', 'importance', 'content', 'source_message_id'],
  renderMemoryRow: renderInstanceMemoryRow,
  emptyListHtml:
    '<div class="alert alert-info"><i class="fas fa-info-circle me-2"></i>No memories for this instance. Click "Add Memory" to create one.</div>',
  parseFormPayload: (formData) => {
    const sourceMsgRaw = (formData.get('source_message_id') || '').toString().trim();
    return {
      memory_type: formData.get('memory_type'),
      importance: parseInt(formData.get('importance'), 10),
      content: (formData.get('content') || '').toString(),
      source_message_id: /^\d+$/.test(sourceMsgRaw) ? sourceMsgRaw : null,
      status: 1,
    };
  },
  fillEditForm: (memory) => {
    document.getElementById('memory-id').value = memory.id;
    document.getElementById('memory-type').value = memory.memory_type;
    document.getElementById('memory-importance').value = memory.importance;
    document.getElementById('memory-source-msg').value = memory.source_message_id || '';
    document.getElementById('memory-content').value = memory.content;
  },
  canToggleArchive: (memory) => Number(memory.status || 1) === 1,
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
    buildPayload: () => buildInstancePayload(mainForm, memoryController).payload,
  });
  bindCancel(snapshotGuard);
  bindSubmit(mainForm, snapshotGuard, memoryController);
  bindGenerateRelationship();
  bindPreviewPanelClose();
  bindMemoryActions(memoryController);
}

init();
