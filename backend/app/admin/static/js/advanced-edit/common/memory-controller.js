function normalizeId(value) {
  return typeof value === 'string' ? value : String(value ?? '');
}

function cloneComparable(memory, fields) {
  const snapshot = {};
  fields.forEach((field) => {
    snapshot[field] = memory[field] ?? null;
  });
  return snapshot;
}

function hasComparableChanged(current, baseline, fields) {
  return fields.some((field) => {
    const left = current[field] ?? null;
    const right = baseline[field] ?? null;
    return left !== right;
  });
}

function formatDatetimeDisplays(selector) {
  document.querySelectorAll(selector).forEach((element) => {
    const isoStr = element.dataset.datetime;
    if (isoStr && isoStr !== 'N/A') {
      try {
        const date = new Date(isoStr);
        const options = {
          year: 'numeric',
          month: 'short',
          day: 'numeric',
          hour: '2-digit',
          minute: '2-digit',
        };
        element.textContent = date.toLocaleString(undefined, options);
      } catch {
        // Keep original text if parsing fails.
      }
    }
  });
}

export function createMemoryController(options) {
  const {
    initialMemories = [],
    comparableFields = [],
    renderMemoryRow,
    emptyListHtml,
    parseFormPayload,
    fillEditForm,
    canToggleArchive = () => true,
    listElementId = 'memories-list',
    modalId = 'memoryModal',
    formId = 'memory-form',
    titleId = 'memoryModalTitle',
    datetimeSelector = '.datetime-display',
    createTitle = 'Add Memory',
    editTitle = 'Edit Memory',
    confirmRemoveNew,
  } = options;

  if (typeof renderMemoryRow !== 'function') {
    throw new Error('renderMemoryRow is required for staged memory controller');
  }
  if (typeof parseFormPayload !== 'function') {
    throw new Error('parseFormPayload is required for staged memory controller');
  }

  let memoryModal = null;
  let listElement = null;
  let editingMemoryId = null;
  let tempIdSeed = 0;

  const baselineById = new Map();
  const stateMemories = initialMemories.map((memory) => {
    const id = normalizeId(memory.id);
    const normalized = {
      ...memory,
      id,
      _isNew: false,
      _archivedPending: false,
    };
    baselineById.set(id, cloneComparable(normalized, comparableFields));
    return normalized;
  });

  function nextTempId() {
    tempIdSeed += 1;
    return `tmp-${tempIdSeed}`;
  }

  function getMemoryById(memoryId) {
    const id = normalizeId(memoryId);
    return stateMemories.find((memory) => memory.id === id) || null;
  }

  function createNewMemory(payload) {
    const id = nextTempId();
    const memory = {
      ...payload,
      id,
      _isNew: true,
      _archivedPending: false,
    };
    stateMemories.push(memory);
    return memory;
  }

  function patchExistingMemory(target, payload) {
    Object.entries(payload).forEach(([key, value]) => {
      target[key] = value;
    });
  }

  function render() {
    if (!listElement) {
      return;
    }
    if (stateMemories.length === 0) {
      listElement.innerHTML = emptyListHtml || '';
      return;
    }
    listElement.innerHTML = stateMemories.map((memory) => renderMemoryRow(memory, { canToggleArchive })).join('');
    formatDatetimeDisplays(datetimeSelector);
  }

  function openMemoryModal(memoryId = null) {
    const form = document.getElementById(formId);
    const title = document.getElementById(titleId);
    if (!form || !title) {
      return;
    }

    form.reset();
    if (memoryId) {
      const memory = getMemoryById(memoryId);
      if (!memory) {
        return;
      }
      editingMemoryId = memory.id;
      title.textContent = editTitle;
      fillEditForm(memory, form);
    } else {
      editingMemoryId = null;
      title.textContent = createTitle;
    }
    memoryModal.show();
  }

  function editMemory(memoryId) {
    openMemoryModal(memoryId);
  }

  async function toggleArchive(memoryId) {
    const memory = getMemoryById(memoryId);
    if (!memory) {
      return;
    }

    if (memory._isNew) {
      if (confirmRemoveNew && typeof confirmRemoveNew === 'function') {
        const ok = await confirmRemoveNew(memory);
        if (!ok) {
          return;
        }
      }
      const index = stateMemories.findIndex((item) => item.id === memory.id);
      if (index >= 0) {
        stateMemories.splice(index, 1);
      }
      render();
      return;
    }

    if (!canToggleArchive(memory)) {
      return;
    }

    memory._archivedPending = !memory._archivedPending;
    render();
  }

  function saveMemory() {
    const form = document.getElementById(formId);
    if (!form) {
      return;
    }
    if (!form.checkValidity()) {
      form.reportValidity();
      return;
    }

    const payload = parseFormPayload(new FormData(form));
    if (editingMemoryId) {
      const memory = getMemoryById(editingMemoryId);
      if (memory) {
        patchExistingMemory(memory, payload);
      }
    } else {
      createNewMemory(payload);
    }

    editingMemoryId = null;
    memoryModal.hide();
    render();
  }

  function buildChanges() {
    const create = [];
    const update = [];
    const archiveIds = [];

    stateMemories.forEach((memory) => {
      if (memory._isNew) {
        const created = {};
        comparableFields.forEach((field) => {
          created[field] = memory[field] ?? null;
        });
        create.push(created);
        return;
      }

      const baseline = baselineById.get(memory.id) || {};
      const baselineStatus = Number(baseline.status ?? memory.status ?? 1);
      if (memory._archivedPending) {
        if (baselineStatus === 1) {
          archiveIds.push(memory.id);
        }
        return;
      }
      if (baselineStatus !== 1) {
        return;
      }

      if (hasComparableChanged(memory, baseline, comparableFields)) {
        const changed = { id: memory.id };
        comparableFields.forEach((field) => {
          changed[field] = memory[field] ?? null;
        });
        update.push(changed);
      }
    });

    return {
      create,
      update,
      archive_ids: archiveIds,
    };
  }

  function init() {
    listElement = document.getElementById(listElementId);
    memoryModal = new bootstrap.Modal(document.getElementById(modalId));
    render();
  }

  return {
    init,
    openMemoryModal,
    editMemory,
    saveMemory,
    toggleArchive,
    buildChanges,
  };
}
