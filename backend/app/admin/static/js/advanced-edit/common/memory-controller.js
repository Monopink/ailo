import { postJson } from './save-flow.js';

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
      } catch (error) {
        // Keep original text if parsing fails.
      }
    }
  });
}

export function createMemoryController(options) {
  const {
    memoriesData = [],
    confirmAction,
    modalId = 'memoryModal',
    formId = 'memory-form',
    titleId = 'memoryModalTitle',
    datetimeSelector = '.datetime-display',
    createTitle = 'Add Memory',
    editTitle = 'Edit Memory',
    fillEditForm,
    onCreateFormReady,
    buildSaveRequest,
    buildDeleteRequest,
    deleteConfirm,
    saveErrorPrefix = 'Failed to save memory',
    deleteErrorPrefix = 'Failed to delete memory',
    onSaved = () => location.reload(),
    onDeleted = () => location.reload(),
  } = options;

  let memoryModal = null;

  function init() {
    memoryModal = new bootstrap.Modal(document.getElementById(modalId));
    formatDatetimeDisplays(datetimeSelector);
  }

  function openMemoryModal(memoryId = null) {
    const form = document.getElementById(formId);
    const title = document.getElementById(titleId);
    form.reset();

    if (memoryId) {
      const memory = memoriesData.find((item) => item.id === memoryId);
      if (!memory) {
        return;
      }
      title.textContent = editTitle;
      fillEditForm(memory, form);
    } else {
      title.textContent = createTitle;
      onCreateFormReady?.(form);
    }
    memoryModal.show();
  }

  function editMemory(memoryId) {
    openMemoryModal(memoryId);
  }

  async function saveMemory() {
    const form = document.getElementById(formId);
    if (!form.checkValidity()) {
      form.reportValidity();
      return;
    }

    const formData = new FormData(form);
    const memoryId = formData.get('memory_id');
    const isEdit = !!memoryId;
    const request = buildSaveRequest({ formData, isEdit, memoryId });

    try {
      const result = await postJson(request.url, request.method, request.payload);
      if (!result.ok) {
        alert(`${saveErrorPrefix}: ${(result.data && result.data.detail) || 'Unknown error'}`);
        return;
      }
      memoryModal.hide();
      onSaved();
    } catch (error) {
      alert(`${saveErrorPrefix}: ${error.message}`);
    }
  }

  async function deleteMemory(memoryId) {
    const ok = await confirmAction(deleteConfirm);
    if (!ok) {
      return;
    }

    const request = buildDeleteRequest(memoryId);
    try {
      const response = await fetch(request.url, { method: request.method || 'DELETE' });
      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        alert(`${deleteErrorPrefix}: ${error.detail || 'Unknown error'}`);
        return;
      }
      onDeleted();
    } catch (error) {
      alert(`${deleteErrorPrefix}: ${error.message}`);
    }
  }

  function exposeGlobals(target = window) {
    target.openMemoryModal = openMemoryModal;
    target.editMemory = editMemory;
    target.saveMemory = saveMemory;
    target.deleteMemory = deleteMemory;
  }

  return {
    init,
    openMemoryModal,
    editMemory,
    saveMemory,
    deleteMemory,
    exposeGlobals,
  };
}
