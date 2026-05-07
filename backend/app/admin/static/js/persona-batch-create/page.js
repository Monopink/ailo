import { withButtonLoading } from '../advanced-edit/common/save-flow.js';

const config = window.ailoPersonaBatchCreateConfig || {};
const submitRowUrl = config.submitRowUrl || '/admin-api/ai/persona-batch/submit-row';
const aiTypeListUrl = config.aiTypeListUrl || '/qiao-dash/api/ai_type?limit=1000';
const importRowsUrl = config.importRowsUrl || '/admin-api/ai/persona-batch/import-rows/consume';
const initialImportToken = typeof config.initialImportToken === 'string' ? config.initialImportToken.trim() : '';
const initialMode = typeof config.initialMode === 'string' ? config.initialMode.trim() : '';

const state = {
  rows: [],
  nextRowId: 1,
  submittingQueue: false,
  activeQueueCount: 0,
  aiTypeItems: [],
};

const AVATAR_OUTPUT_SIZE = 512;
const AVATAR_OUTPUT_MIME = 'image/webp';
const AVATAR_MAX_UPLOAD_BYTES = 1024 * 1024;
const AVATAR_WEBP_QUALITY_STEPS = [0.9, 0.85, 0.8, 0.75, 0.7, 0.65, 0.6, 0.55, 0.5];
const GENDER_OPTIONS = [
  { value: '', label: '未设置' },
  { value: '1', label: '男' },
  { value: '2', label: '女' },
  { value: '3', label: '其他' },
];
const REUSABLE_OPTIONS = [
  { value: '1', label: '可复用' },
  { value: '0', label: '单次使用' },
];

const elements = {
  typeSelect: document.getElementById('typeSelect'),
  batchGender: document.getElementById('batchGender'),
  batchIsReusable: document.getElementById('batchIsReusable'),
  batchCount: document.getElementById('batchCount'),
  addRowsBtn: document.getElementById('addRowsBtn'),
  removeSuccessBtn: document.getElementById('removeSuccessBtn'),
  submitDraftBtn: document.getElementById('submitDraftBtn'),
  retryFailedBtn: document.getElementById('retryFailedBtn'),
  submitAllBtn: document.getElementById('submitAllBtn'),
  queueRowsBody: document.getElementById('queueRowsBody'),
  queueSummary: document.getElementById('queueSummary'),
  queueStatusMessage: document.getElementById('queueStatusMessage'),
};

function escapeHtml(value) {
  const text = value === null || value === undefined ? '' : String(value);
  return text
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function countRowsByStatus(status) {
  return state.rows.filter((row) => row.status === status).length;
}

function normalizeGenderValue(rawValue) {
  if (rawValue === null || rawValue === undefined) {
    return null;
  }
  const text = String(rawValue).trim();
  if (!text) {
    return null;
  }
  if (text === '1' || text === '2' || text === '3') {
    return Number(text);
  }
  return null;
}

function normalizeNullableText(value) {
  if (value === null || value === undefined) {
    return '';
  }
  return String(value);
}

function normalizeIsReusableValue(rawValue) {
  if (rawValue === null || rawValue === undefined) {
    return 1;
  }
  const text = String(rawValue).trim();
  if (text === '0') {
    return 0;
  }
  return 1;
}

function normalizeTagsInputValue(rawValue) {
  if (Array.isArray(rawValue)) {
    const deduped = [];
    const seen = new Set();
    rawValue.forEach((item) => {
      const text = String(item || '').trim();
      if (!text || seen.has(text)) {
        return;
      }
      seen.add(text);
      deduped.push(text);
    });
    return deduped;
  }
  if (rawValue === null || rawValue === undefined) {
    return [];
  }
  const text = String(rawValue).trim();
  if (!text) {
    return [];
  }
  return normalizeTagsInputValue(text.split(/[,\n，]/g));
}

function parseTagsFromTextInput(inputText) {
  if (inputText === null || inputText === undefined) {
    return [];
  }
  return normalizeTagsInputValue(String(inputText).split(/[,\n，]/g));
}

function tagsToSubmitValue(tags) {
  const normalized = normalizeTagsInputValue(tags);
  return normalized.join(',');
}

function parseIntOrNull(rawValue) {
  if (rawValue === null || rawValue === undefined || rawValue === '') {
    return null;
  }
  const value = Number(rawValue);
  if (!Number.isInteger(value)) {
    return null;
  }
  return value;
}

function createDraftRow(typeId, typeName, gender, isReusable, region, bio, tags, remark) {
  return {
    localRowId: `row-${state.nextRowId++}`,
    typeId,
    typeName,
    nickname: '',
    gender,
    isReusable,
    region,
    bio,
    tags: normalizeTagsInputValue(tags),
    remark,
    avatarFile: null,
    avatarPreviewUrl: '',
    status: 'draft',
    personaId: null,
    profileId: null,
    failedStep: null,
    lastError: '',
  };
}

function getFirstImageFile(dataTransferLike) {
  if (!dataTransferLike) {
    return null;
  }
  const fileList = Array.from(dataTransferLike.files || []);
  const fromFiles = fileList.find((file) => file && typeof file.type === 'string' && file.type.startsWith('image/'));
  if (fromFiles) {
    return fromFiles;
  }
  const items = Array.from(dataTransferLike.items || []);
  for (const item of items) {
    if (item.kind === 'file' && typeof item.type === 'string' && item.type.startsWith('image/')) {
      const file = item.getAsFile();
      if (file) {
        return file;
      }
    }
  }
  return null;
}

function parseResponseJsonSafe(response) {
  return response
    .json()
    .then((payload) => payload)
    .catch(() => ({}));
}

function buildOutputFileName(originalName) {
  const rawName = typeof originalName === 'string' ? originalName.trim() : '';
  const baseName = rawName.replace(/\.[^.]+$/, '');
  const resolvedBaseName = baseName || 'avatar';
  return `${resolvedBaseName}.webp`;
}

function encodeCanvasToBlob(canvas, mimeType, quality) {
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => {
        if (blob) {
          resolve(blob);
          return;
        }
        reject(new Error('图片编码失败。'));
      },
      mimeType,
      quality
    );
  });
}

function loadImageElementFromFile(file) {
  return new Promise((resolve, reject) => {
    const objectUrl = window.URL.createObjectURL(file);
    const image = new Image();
    image.onload = () => {
      window.URL.revokeObjectURL(objectUrl);
      resolve(image);
    };
    image.onerror = () => {
      window.URL.revokeObjectURL(objectUrl);
      reject(new Error('无法解析图片内容。'));
    };
    image.src = objectUrl;
  });
}

async function buildAvatarUploadFile(sourceFile) {
  const image = await loadImageElementFromFile(sourceFile);
  const naturalWidth = image.naturalWidth;
  const naturalHeight = image.naturalHeight;
  if (naturalWidth <= 0 || naturalHeight <= 0) {
    throw new Error('图片尺寸无效。');
  }

  const cropSize = Math.min(naturalWidth, naturalHeight);
  const cropX = Math.floor((naturalWidth - cropSize) / 2);
  const cropY = Math.floor((naturalHeight - cropSize) / 2);

  const canvas = document.createElement('canvas');
  canvas.width = AVATAR_OUTPUT_SIZE;
  canvas.height = AVATAR_OUTPUT_SIZE;
  const ctx = canvas.getContext('2d');
  if (!ctx) {
    throw new Error('图像处理上下文不可用。');
  }
  ctx.drawImage(image, cropX, cropY, cropSize, cropSize, 0, 0, AVATAR_OUTPUT_SIZE, AVATAR_OUTPUT_SIZE);

  let bestBlob = null;
  for (const quality of AVATAR_WEBP_QUALITY_STEPS) {
    const encodedBlob = await encodeCanvasToBlob(canvas, AVATAR_OUTPUT_MIME, quality);
    if (!bestBlob || encodedBlob.size < bestBlob.size) {
      bestBlob = encodedBlob;
    }
    if (encodedBlob.size <= AVATAR_MAX_UPLOAD_BYTES) {
      return new File([encodedBlob], buildOutputFileName(sourceFile.name), {
        type: encodedBlob.type || AVATAR_OUTPUT_MIME,
        lastModified: Date.now(),
      });
    }
  }

  if (bestBlob) {
    const sizeKb = Math.ceil(bestBlob.size / 1024);
    throw new Error(`处理后的头像约 ${sizeKb}KB，仍超过 1MB 限制。`);
  }
  throw new Error('头像处理失败。');
}

function getStateBadge(row) {
  if (row.status === 'success') {
    return '<span class="status-pill status-pill-success">成功</span>';
  }
  if (row.status === 'editing') {
    return '<span class="status-pill status-pill-draft">编辑</span>';
  }
  if (row.status === 'failed') {
    return '<span class="status-pill status-pill-failed">失败</span>';
  }
  if (row.status === 'submitting') {
    return '<span class="status-pill status-pill-submitting">提交中</span>';
  }
  return '<span class="status-pill status-pill-draft">草稿</span>';
}

function createRowActionsHtml(row) {
  const buttonText = row.status === 'failed' ? '重试' : '提交';
  const buttonClass = row.status === 'failed' ? 'btn-outline-warning' : 'btn-primary';
  return `<button class="btn ${buttonClass} row-submit-btn" type="button" data-row-id="${escapeHtml(
    row.localRowId
  )}">${buttonText}</button>`;
}

function rowAvatarHint(row) {
  if (row.avatarFile) {
    return `文件：${row.avatarFile.name}`;
  }
  if (row.avatarPreviewUrl) {
    return '头像已上传。';
  }
  return '点击选择、拖拽上传，或聚焦后粘贴图片。';
}

function canClearAvatar(row) {
  return Boolean(row.avatarFile || row.avatarPreviewUrl);
}

function shouldDisableRowInputs(row) {
  return row.status === 'submitting';
}

function markRowAsEdited(row) {
  let changed = false;
  if (row.status === 'success') {
    row.status = row.personaId ? 'editing' : 'draft';
    changed = true;
  }
  if (row.status === 'failed') {
    row.failedStep = null;
    row.lastError = '';
    changed = true;
  }
  return changed;
}

function buildGenderSelectHtml(localRowId, currentGender, disabledAttr) {
  const currentValue = currentGender === null || currentGender === undefined ? '' : String(currentGender);
  const optionsHtml = GENDER_OPTIONS.map((option) => {
    const selected = option.value === currentValue ? 'selected' : '';
    return `<option value="${option.value}" ${selected}>${option.label}</option>`;
  }).join('');
  return `<select class="form-select row-gender-select" data-row-id="${escapeHtml(
    localRowId
  )}" ${disabledAttr}>${optionsHtml}</select>`;
}

function buildIsReusableSelectHtml(localRowId, currentIsReusable, disabledAttr) {
  const currentValue = currentIsReusable === 0 ? '0' : '1';
  const optionsHtml = REUSABLE_OPTIONS.map((option) => {
    const selected = option.value === currentValue ? 'selected' : '';
    return `<option value="${option.value}" ${selected}>${option.label}</option>`;
  }).join('');
  return `<select class="form-select row-is-reusable-select" data-row-id="${escapeHtml(
    localRowId
  )}" ${disabledAttr}>${optionsHtml}</select>`;
}

function buildTagsEditorHtml(localRowId, tags, disabledAttr) {
  const normalized = normalizeTagsInputValue(tags);
  const chipsHtml = normalized
    .map(
      (tag, index) => `
      <span class="row-tag-chip">
        <span class="row-tag-chip-text" title="${escapeHtml(tag)}">${escapeHtml(tag)}</span>
        <button class="row-tag-remove-btn"
                type="button"
                aria-label="移除标签"
                data-row-id="${escapeHtml(localRowId)}"
                data-tag-index="${index}"
                ${disabledAttr}>
          ×
        </button>
      </span>
    `
    )
    .join('');
  const emptyHtml = normalized.length === 0 ? '<span class="row-tags-empty">回车或逗号添加标签</span>' : '';
  return `
    <div class="row-tags-editor">
      ${chipsHtml}
      ${emptyHtml}
      <input class="row-tags-input row-tags-editor-input"
             type="text"
             placeholder="输入标签后回车"
             data-row-id="${escapeHtml(localRowId)}"
             ${disabledAttr}>
    </div>
  `;
}

function renderRows() {
  if (state.rows.length === 0) {
    elements.queueRowsBody.innerHTML = '<tr><td colspan="13" class="text-center text-muted">暂无条目。</td></tr>';
    return;
  }

  const html = state.rows
    .map((row, index) => {
      const disabledAttr = shouldDisableRowInputs(row) ? 'disabled' : '';
      const preview = row.avatarPreviewUrl
        ? `<img src="${escapeHtml(row.avatarPreviewUrl)}" alt="头像预览" class="avatar-preview">`
        : '<div class="avatar-preview d-flex align-items-center justify-content-center text-muted">-</div>';
      const avatarHint = rowAvatarHint(row);
      const idsText = row.personaId ? `人设ID: ${row.personaId}` : '-';
      const profileText = row.profileId ? `资料ID: ${row.profileId}` : '-';
      return `
        <tr data-row-id="${escapeHtml(row.localRowId)}">
          <td>${index + 1}</td>
          <td class="row-status-cell">${getStateBadge(row)}</td>
          <td>
            <div>${escapeHtml(row.typeName)} (#${row.typeId})</div>
            <div class="small text-muted">${idsText}, ${profileText}</div>
          </td>
          <td>
            <div class="d-flex gap-2 align-items-start">
              <div class="avatar-preview-wrap">
                ${preview}
              </div>
              <div class="avatar-content-wrap">
                <div class="avatar-drop-zone row-avatar-drop-zone" tabindex="0" data-row-id="${escapeHtml(
                  row.localRowId
                )}">
                  <input class="form-control form-control-sm row-avatar-input" data-row-id="${escapeHtml(
                    row.localRowId
                  )}" type="file" accept="image/*" ${disabledAttr}>
                  <div class="d-flex align-items-center gap-2 mt-1">
                    <div class="small text-muted flex-grow-1 avatar-hint" title="${escapeHtml(avatarHint)}">
                      ${escapeHtml(avatarHint)}
                    </div>
                    <button class="btn btn-outline-secondary btn-sm py-0 px-2 row-avatar-clear-btn"
                            type="button"
                            data-row-id="${escapeHtml(row.localRowId)}"
                            ${row.status === 'submitting' || !canClearAvatar(row) ? 'disabled' : ''}>
                      清空
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </td>
          <td>
            <input class="form-control row-nickname-input" data-row-id="${escapeHtml(
              row.localRowId
            )}" value="${escapeHtml(row.nickname)}" ${disabledAttr}>
          </td>
          <td>
            ${buildGenderSelectHtml(row.localRowId, row.gender, disabledAttr)}
          </td>
          <td>
            <input class="form-control row-bio-input"
                   data-row-id="${escapeHtml(row.localRowId)}"
                   value="${escapeHtml(row.bio || '')}"
                   ${disabledAttr}>
          </td>
          <td>
            <input class="form-control row-region-input"
                   data-row-id="${escapeHtml(row.localRowId)}"
                   value="${escapeHtml(row.region || '')}"
                   ${disabledAttr}>
          </td>
          <td>
            ${buildTagsEditorHtml(row.localRowId, row.tags, disabledAttr)}
          </td>
          <td>
            <input class="form-control row-remark-input"
                   data-row-id="${escapeHtml(row.localRowId)}"
                   value="${escapeHtml(row.remark || '')}"
                   ${disabledAttr}>
          </td>
          <td>
            ${buildIsReusableSelectHtml(row.localRowId, row.isReusable, disabledAttr)}
          </td>
          <td class="small text-danger row-error-cell">${escapeHtml(row.lastError || '')}</td>
          <td class="text-nowrap operation-col">
            ${createRowActionsHtml(row)}
            <button class="btn btn-outline-danger row-delete-btn ms-1" type="button" data-row-id="${escapeHtml(
              row.localRowId
            )}" ${row.status === 'submitting' ? 'disabled' : ''}>移除</button>
          </td>
        </tr>
      `;
    })
    .join('');

  elements.queueRowsBody.innerHTML = html;
  bindRowEvents();
}

function updateQueueActions() {
  const draftCount = countRowsByStatus('draft');
  const editingCount = countRowsByStatus('editing');
  const failedCount = countRowsByStatus('failed');
  const successCount = countRowsByStatus('success');
  const submittingCount = countRowsByStatus('submitting');

  elements.queueSummary.textContent = `草稿：${draftCount}，编辑：${editingCount}，失败：${failedCount}，成功：${successCount}，提交中：${submittingCount}`;

  const disableByQueue = state.submittingQueue || state.activeQueueCount > 0;
  elements.submitDraftBtn.disabled = disableByQueue || draftCount + editingCount === 0;
  elements.retryFailedBtn.disabled = disableByQueue || failedCount === 0;
  elements.submitAllBtn.disabled = disableByQueue || draftCount + editingCount + failedCount === 0;
  elements.removeSuccessBtn.disabled = disableByQueue || successCount === 0;

  if (failedCount > 0) {
    elements.retryFailedBtn.classList.remove('d-none');
    elements.submitAllBtn.classList.remove('d-none');
  } else {
    elements.retryFailedBtn.classList.add('d-none');
    elements.submitAllBtn.classList.add('d-none');
  }
}

function refreshUi() {
  renderRows();
  updateQueueActions();
}

function setQueueStatusMessage(message) {
  elements.queueStatusMessage.textContent = message;
}

function findRow(localRowId) {
  return state.rows.find((row) => row.localRowId === localRowId) || null;
}

async function setRowAvatarFile(row, file) {
  markRowAsEdited(row);
  if (!file || !(file.type || '').startsWith('image/')) {
    row.lastError = '仅支持图片文件。';
    row.status = 'failed';
    refreshUi();
    return;
  }
  try {
    const uploadFile = await buildAvatarUploadFile(file);
    row.avatarFile = uploadFile;
    const reader = new FileReader();
    reader.onload = () => {
      row.avatarPreviewUrl = typeof reader.result === 'string' ? reader.result : '';
      if (row.status === 'failed') {
        row.failedStep = null;
      }
      row.lastError = '';
      refreshUi();
    };
    reader.onerror = () => {
      row.lastError = '读取处理后图片失败。';
      row.status = 'failed';
      refreshUi();
    };
    reader.readAsDataURL(uploadFile);
  } catch (error) {
    row.lastError = error instanceof Error ? error.message : '头像处理失败。';
    row.status = 'failed';
    refreshUi();
  }
}

function clearRowAvatar(row) {
  markRowAsEdited(row);
  row.avatarFile = null;
  row.avatarPreviewUrl = '';
  row.lastError = '';
  refreshUi();
}

function bindRowEvents() {
  const applyRowEditedState = (eventTarget, row) => {
    const previousStatus = row.status;
    markRowAsEdited(row);
    if (previousStatus !== row.status) {
      const tableRow = eventTarget.closest('tr');
      const statusCell = tableRow?.querySelector('.row-status-cell');
      if (statusCell) {
        statusCell.innerHTML = getStateBadge(row);
      }
    }
    if (!row.lastError) {
      const tableRow = eventTarget.closest('tr');
      const errorCell = tableRow?.querySelector('.row-error-cell');
      if (errorCell) {
        errorCell.textContent = '';
      }
    }
    updateQueueActions();
  };

  elements.queueRowsBody.querySelectorAll('.row-nickname-input').forEach((inputEl) => {
    inputEl.addEventListener('input', (event) => {
      const row = findRow(event.target.dataset.rowId);
      if (!row) {
        return;
      }
      row.nickname = event.target.value;
      applyRowEditedState(event.target, row);
    });
  });

  elements.queueRowsBody.querySelectorAll('.row-gender-select').forEach((selectEl) => {
    selectEl.addEventListener('change', (event) => {
      const row = findRow(event.target.dataset.rowId);
      if (!row) {
        return;
      }
      row.gender = normalizeGenderValue(event.target.value);
      applyRowEditedState(event.target, row);
    });
  });

  elements.queueRowsBody.querySelectorAll('.row-is-reusable-select').forEach((selectEl) => {
    selectEl.addEventListener('change', (event) => {
      const row = findRow(event.target.dataset.rowId);
      if (!row) {
        return;
      }
      row.isReusable = normalizeIsReusableValue(event.target.value);
      applyRowEditedState(event.target, row);
    });
  });

  elements.queueRowsBody.querySelectorAll('.row-region-input').forEach((inputEl) => {
    inputEl.addEventListener('input', (event) => {
      const row = findRow(event.target.dataset.rowId);
      if (!row) {
        return;
      }
      row.region = event.target.value;
      applyRowEditedState(event.target, row);
    });
  });

  elements.queueRowsBody.querySelectorAll('.row-bio-input').forEach((inputEl) => {
    inputEl.addEventListener('input', (event) => {
      const row = findRow(event.target.dataset.rowId);
      if (!row) {
        return;
      }
      row.bio = event.target.value;
      applyRowEditedState(event.target, row);
    });
  });

  const appendTagsToRow = (eventTarget, row, rawTags) => {
    const incomingTags = normalizeTagsInputValue(rawTags);
    if (incomingTags.length === 0) {
      return false;
    }
    const current = normalizeTagsInputValue(row.tags);
    const seen = new Set(current);
    let changed = false;
    incomingTags.forEach((tag) => {
      if (seen.has(tag)) {
        return;
      }
      seen.add(tag);
      current.push(tag);
      changed = true;
    });
    if (!changed) {
      return false;
    }
    row.tags = current;
    applyRowEditedState(eventTarget, row);
    refreshUi();
    return true;
  };

  const removeTagFromRow = (eventTarget, row, indexValue) => {
    const index = Number(indexValue);
    if (!Number.isInteger(index) || index < 0) {
      return;
    }
    const current = normalizeTagsInputValue(row.tags);
    if (index >= current.length) {
      return;
    }
    current.splice(index, 1);
    row.tags = current;
    applyRowEditedState(eventTarget, row);
    refreshUi();
  };

  elements.queueRowsBody.querySelectorAll('.row-tags-editor-input').forEach((inputEl) => {
    inputEl.addEventListener('keydown', (event) => {
      const row = findRow(event.target.dataset.rowId);
      if (!row) {
        return;
      }
      if ((event.key === 'Enter' || event.key === ',') && !event.isComposing) {
        event.preventDefault();
        const inputText = event.target.value || '';
        const candidateTags = parseTagsFromTextInput(inputText);
        if (appendTagsToRow(event.target, row, candidateTags)) {
          event.target.value = '';
        }
        return;
      }
      if (event.key === 'Backspace' && !event.target.value) {
        const current = normalizeTagsInputValue(row.tags);
        if (current.length === 0) {
          return;
        }
        event.preventDefault();
        current.pop();
        row.tags = current;
        applyRowEditedState(event.target, row);
        refreshUi();
      }
    });

    inputEl.addEventListener('blur', (event) => {
      const row = findRow(event.target.dataset.rowId);
      if (!row) {
        return;
      }
      const inputText = event.target.value || '';
      if (!inputText.trim()) {
        return;
      }
      const candidateTags = parseTagsFromTextInput(inputText);
      if (appendTagsToRow(event.target, row, candidateTags)) {
        event.target.value = '';
      }
    });

    inputEl.addEventListener('paste', (event) => {
      const row = findRow(event.target.dataset.rowId);
      if (!row) {
        return;
      }
      const pastedText = event.clipboardData?.getData('text') || '';
      const candidateTags = parseTagsFromTextInput(pastedText);
      if (candidateTags.length === 0) {
        return;
      }
      event.preventDefault();
      appendTagsToRow(event.target, row, candidateTags);
      event.target.value = '';
    });
  });

  elements.queueRowsBody.querySelectorAll('.row-tag-remove-btn').forEach((buttonEl) => {
    buttonEl.addEventListener('click', (event) => {
      const row = findRow(event.currentTarget.dataset.rowId);
      if (!row) {
        return;
      }
      removeTagFromRow(event.currentTarget, row, event.currentTarget.dataset.tagIndex);
    });
  });

  elements.queueRowsBody.querySelectorAll('.row-remark-input').forEach((inputEl) => {
    inputEl.addEventListener('input', (event) => {
      const row = findRow(event.target.dataset.rowId);
      if (!row) {
        return;
      }
      row.remark = event.target.value;
      applyRowEditedState(event.target, row);
    });
  });

  elements.queueRowsBody.querySelectorAll('.row-avatar-input').forEach((inputEl) => {
    inputEl.addEventListener('change', async (event) => {
      const row = findRow(event.target.dataset.rowId);
      if (!row) {
        return;
      }
      const file = event.target.files && event.target.files[0];
      if (!file) {
        return;
      }
      await setRowAvatarFile(row, file);
    });
  });

  elements.queueRowsBody.querySelectorAll('.row-avatar-clear-btn').forEach((buttonEl) => {
    buttonEl.addEventListener('click', (event) => {
      const row = findRow(event.currentTarget.dataset.rowId);
      if (!row) {
        return;
      }
      clearRowAvatar(row);
    });
  });

  elements.queueRowsBody.querySelectorAll('.row-avatar-drop-zone').forEach((zoneEl) => {
    const activate = (active) => zoneEl.classList.toggle('is-dragover', active);
    ['dragenter', 'dragover'].forEach((name) => {
      zoneEl.addEventListener(name, (event) => {
        event.preventDefault();
        event.stopPropagation();
        activate(true);
      });
    });
    ['dragleave', 'dragend'].forEach((name) => {
      zoneEl.addEventListener(name, (event) => {
        event.preventDefault();
        event.stopPropagation();
        activate(false);
      });
    });
    zoneEl.addEventListener('drop', async (event) => {
      event.preventDefault();
      event.stopPropagation();
      activate(false);
      const row = findRow(event.currentTarget.dataset.rowId);
      if (!row) {
        return;
      }
      const file = getFirstImageFile(event.dataTransfer);
      if (!file) {
        row.lastError = '拖拽内容中未找到图片文件。';
        row.status = 'failed';
        refreshUi();
        return;
      }
      await setRowAvatarFile(row, file);
    });
    zoneEl.addEventListener('paste', async (event) => {
      const row = findRow(event.currentTarget.dataset.rowId);
      if (!row) {
        return;
      }
      const file = getFirstImageFile(event.clipboardData);
      if (!file) {
        return;
      }
      event.preventDefault();
      await setRowAvatarFile(row, file);
    });
  });

  elements.queueRowsBody.querySelectorAll('.row-submit-btn').forEach((buttonEl) => {
    buttonEl.addEventListener('click', async (event) => {
      const localRowId = event.currentTarget.dataset.rowId;
      const row = findRow(localRowId);
      if (!row) {
        return;
      }
      await submitOneRow(row);
    });
  });

  elements.queueRowsBody.querySelectorAll('.row-delete-btn').forEach((buttonEl) => {
    buttonEl.addEventListener('click', (event) => {
      const localRowId = event.currentTarget.dataset.rowId;
      state.rows = state.rows.filter((row) => row.localRowId !== localRowId);
      refreshUi();
    });
  });
}

async function submitOneRow(row) {
  if (row.status !== 'draft' && row.status !== 'editing' && row.status !== 'failed' && row.status !== 'success') {
    return;
  }
  row.status = 'submitting';
  row.lastError = '';
  refreshUi();

  const formData = new FormData();
  formData.append('local_row_id', row.localRowId);
  formData.append('type_id', String(row.typeId));
  formData.append('nickname', row.nickname || '');
  formData.append('gender', row.gender === null || row.gender === undefined ? '' : String(row.gender));
  formData.append('is_reusable', String(row.isReusable === 0 ? 0 : 1));
  formData.append('region', row.region || '');
  formData.append('bio', row.bio || '');
  formData.append('tags', tagsToSubmitValue(row.tags));
  formData.append('remark', row.remark || '');
  if (row.personaId) {
    formData.append('persona_id', String(row.personaId));
  }
  if (row.profileId) {
    formData.append('profile_id', String(row.profileId));
  }
  if (row.avatarFile) {
    formData.append('avatar_file', row.avatarFile, row.avatarFile.name || 'avatar.webp');
  }

  try {
    const response = await fetch(submitRowUrl, {
      method: 'POST',
      body: formData,
      credentials: 'same-origin',
    });
    const payload = await parseResponseJsonSafe(response);
    if (!response.ok) {
      throw new Error(payload.detail || payload.message || `HTTP ${response.status}`);
    }

    if (payload.status === 'success') {
      row.status = 'success';
      row.lastError = '';
      row.failedStep = null;
      row.personaId = payload.persona_id || row.personaId;
      row.profileId = payload.profile_id || row.profileId;
      row.avatarFile = null;
      if (typeof payload.avatar_url === 'string' && payload.avatar_url) {
        row.avatarPreviewUrl = payload.avatar_url;
      }
      refreshUi();
      return;
    }

    row.status = 'failed';
    row.personaId = payload.persona_id || row.personaId;
    row.profileId = payload.profile_id || row.profileId;
    row.failedStep = payload.failed_step || null;
    row.lastError = payload.error_message || '提交失败';
    refreshUi();
  } catch (error) {
    row.status = 'failed';
    row.lastError = error instanceof Error ? error.message : '提交失败';
    refreshUi();
  }
}

async function submitRowsByFilter(filterFn, buttonEl, loadingText, doneMessage) {
  const targetRows = state.rows.filter(filterFn);
  if (targetRows.length === 0) {
    setQueueStatusMessage('当前操作没有可处理的条目。');
    return;
  }
  state.submittingQueue = true;
  state.activeQueueCount = targetRows.length;
  refreshUi();
  setQueueStatusMessage(`正在提交 ${targetRows.length} 条...`);

  let successCount = 0;
  let failedCount = 0;
  await withButtonLoading(buttonEl, loadingText, async () => {
    for (const row of targetRows) {
      await submitOneRow(row);
      if (row.status === 'success') {
        successCount += 1;
      } else if (row.status === 'failed') {
        failedCount += 1;
      }
      state.activeQueueCount -= 1;
      updateQueueActions();
    }
  });

  state.submittingQueue = false;
  state.activeQueueCount = 0;
  refreshUi();
  setQueueStatusMessage(`${doneMessage}完成。成功=${successCount}，失败=${failedCount}`);
}

function addDraftRows() {
  const typeValue = elements.typeSelect.value;
  if (!typeValue) {
    setQueueStatusMessage('请先选择 AI 类型。');
    return;
  }
  const defaultGender = normalizeGenderValue(elements.batchGender?.value);
  const defaultIsReusable = normalizeIsReusableValue(elements.batchIsReusable?.value);
  const countValue = Number(elements.batchCount.value);
  const count = Number.isFinite(countValue) ? Math.max(1, Math.min(100, Math.floor(countValue))) : 1;
  const selectedOption = elements.typeSelect.options[elements.typeSelect.selectedIndex];
  const typeName = selectedOption ? selectedOption.textContent : `类型 ${typeValue}`;

  for (let i = 0; i < count; i += 1) {
    state.rows.push(createDraftRow(Number(typeValue), typeName, defaultGender, defaultIsReusable, '', '', '', ''));
  }
  setQueueStatusMessage(`已添加 ${count} 条草稿。`);
  refreshUi();
}

function removeSuccessRows() {
  const before = state.rows.length;
  state.rows = state.rows.filter((row) => row.status !== 'success');
  const removed = before - state.rows.length;
  setQueueStatusMessage(`已移除 ${removed} 条成功记录。`);
  refreshUi();
}

async function loadAiTypes() {
  const response = await fetch(aiTypeListUrl, { credentials: 'same-origin' });
  if (!response.ok) {
    throw new Error('加载 AI 类型失败');
  }
  const payload = await response.json();
  const items = Array.isArray(payload.items) ? payload.items : [];
  state.aiTypeItems = items
    .filter((item) => item && item.id !== undefined && item.id !== null)
    .map((item) => ({
      id: String(item.id),
      text: item.display_name ? String(item.display_name) : `Type ${item.id}`,
      meta: {},
    }));

  elements.typeSelect.innerHTML = '';
  state.aiTypeItems.forEach((item) => {
    const option = document.createElement('option');
    option.value = item.id;
    option.textContent = item.text;
    elements.typeSelect.appendChild(option);
  });

  const searchSelect = window.ailoSearchSelect;
  if (searchSelect && typeof searchSelect.initSearchSelect === 'function') {
    searchSelect.initSearchSelect({
      element: elements.typeSelect,
      items: state.aiTypeItems,
      placeholder: String(elements.typeSelect.dataset.placeholder || '搜索 AI 类型'),
      allowClear: false,
      minimumInputLength: 0,
      language: {
        noResults: '未找到 AI 类型。',
      },
    });
  }

  if (items.length === 0) {
    const option = document.createElement('option');
    option.value = '';
    option.textContent = '暂无可用 AI 类型';
    elements.typeSelect.appendChild(option);
    elements.typeSelect.disabled = true;
    elements.addRowsBtn.disabled = true;
  }
}

async function loadImportedRows() {
  if (!initialImportToken) {
    if (initialMode === 'edit') {
      setQueueStatusMessage('编辑模式：请在 Personas 列表勾选条目后，使用 with selected -> 批量编辑 导入。');
    }
    return;
  }

  const response = await fetch(`${importRowsUrl}?import_token=${encodeURIComponent(initialImportToken)}`, {
    method: 'POST',
    credentials: 'same-origin',
  });
  const payload = await parseResponseJsonSafe(response);
  if (!response.ok) {
    throw new Error(payload.detail || payload.message || '导入待编辑条目失败');
  }
  const items = Array.isArray(payload.items) ? payload.items : [];
  if (items.length === 0) {
    setQueueStatusMessage('导入完成，但未找到可编辑条目。');
    return;
  }

  let importedCount = 0;
  items.forEach((item) => {
    const typeId = parseIntOrNull(item.type_id);
    if (typeId === null) {
      return;
    }
    const row = createDraftRow(
      typeId,
      normalizeNullableText(item.type_name) || `类型 ${typeId}`,
      normalizeGenderValue(item.gender),
      normalizeIsReusableValue(item.is_reusable),
      normalizeNullableText(item.region),
      normalizeNullableText(item.bio),
      Array.isArray(item.tags) ? item.tags : normalizeNullableText(item.tags),
      normalizeNullableText(item.remark)
    );
    row.nickname = normalizeNullableText(item.nickname);
    row.personaId = normalizeNullableText(item.persona_id) || null;
    row.profileId = normalizeNullableText(item.profile_id) || null;
    row.avatarPreviewUrl = normalizeNullableText(item.avatar_url);
    row.status = 'editing';
    row.lastError = '';
    row.failedStep = null;
    state.rows.push(row);
    importedCount += 1;
  });

  setQueueStatusMessage(`已导入 ${importedCount} 条待编辑记录。`);
}

function bindPageEvents() {
  elements.addRowsBtn.addEventListener('click', addDraftRows);
  elements.removeSuccessBtn.addEventListener('click', removeSuccessRows);

  elements.submitDraftBtn.addEventListener('click', async () => {
    await submitRowsByFilter(
      (row) => row.status === 'draft' || row.status === 'editing',
      elements.submitDraftBtn,
      '<span class="spinner-border spinner-border-sm me-2"></span>提交中...',
      '提交'
    );
  });

  elements.retryFailedBtn.addEventListener('click', async () => {
    await submitRowsByFilter(
      (row) => row.status === 'failed',
      elements.retryFailedBtn,
      '<span class="spinner-border spinner-border-sm me-2"></span>重试中...',
      '重试'
    );
  });

  elements.submitAllBtn.addEventListener('click', async () => {
    await submitRowsByFilter(
      (row) => row.status === 'draft' || row.status === 'editing' || row.status === 'failed',
      elements.submitAllBtn,
      '<span class="spinner-border spinner-border-sm me-2"></span>处理中...',
      '提交和重试'
    );
  });
}

async function init() {
  bindPageEvents();
  try {
    await loadAiTypes();
    await loadImportedRows();
    if (!initialImportToken) {
      setQueueStatusMessage('已就绪。');
    }
  } catch (error) {
    setQueueStatusMessage(error instanceof Error ? error.message : '页面初始化失败。');
  }
  refreshUi();
}

init();
