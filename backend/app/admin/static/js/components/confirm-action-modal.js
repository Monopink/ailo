const resolveText = (value, fallback) => {
  if (typeof value === 'string' && value.trim() !== '') {
    return value;
  }
  return fallback;
};

const ensureModalElement = (modalId) => {
  const existing = document.getElementById(modalId);
  if (existing instanceof HTMLElement) {
    return existing;
  }

  const wrapper = document.createElement('div');
  wrapper.innerHTML = `
    <div class="modal fade" id="${modalId}" tabindex="-1" aria-hidden="true">
      <div class="modal-dialog modal-dialog-centered">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title" id="${modalId}-title"></h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
          </div>
          <div class="modal-body">
            <div id="${modalId}-body"></div>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-outline-secondary" id="${modalId}-cancel" data-bs-dismiss="modal"></button>
            <button type="button" class="btn btn-primary" id="${modalId}-confirm"></button>
          </div>
        </div>
      </div>
    </div>
  `;
  const created = wrapper.firstElementChild;
  if (!(created instanceof HTMLElement)) {
    throw new Error('Failed to create modal element');
  }
  document.body.appendChild(created);
  return created;
};

export const createConfirmActionModal = ({
  modalId,
  cancelText = 'Cancel',
  defaultErrorMessage = 'Operation failed',
  showAlert,
  reloadOnSuccess = false,
}) => {
  const resolvedModalId = resolveText(modalId, 'confirm-action-modal');
  const modalEl = ensureModalElement(resolvedModalId);
  const titleEl = document.getElementById(`${resolvedModalId}-title`);
  const bodyEl = document.getElementById(`${resolvedModalId}-body`);
  const cancelEl = document.getElementById(`${resolvedModalId}-cancel`);
  const confirmEl = document.getElementById(`${resolvedModalId}-confirm`);

  if (
    !(titleEl instanceof HTMLElement) ||
    !(bodyEl instanceof HTMLElement) ||
    !(cancelEl instanceof HTMLButtonElement) ||
    !(confirmEl instanceof HTMLButtonElement)
  ) {
    throw new Error('Modal element bindings are invalid');
  }

  const modal =
    typeof window !== 'undefined' && window.bootstrap && typeof window.bootstrap.Modal === 'function'
      ? new window.bootstrap.Modal(modalEl)
      : null;
  if (modal === null) {
    throw new Error('Bootstrap modal is unavailable');
  }

  cancelEl.textContent = resolveText(cancelText, 'Cancel');
  let submitHandler = null;

  confirmEl.addEventListener('click', async () => {
    if (typeof submitHandler !== 'function') {
      return;
    }
    confirmEl.disabled = true;
    try {
      await submitHandler();
      modal.hide();
      if (reloadOnSuccess) {
        window.location.reload();
      }
    } catch (error) {
      const message =
        error instanceof Error && error.message ? error.message : resolveText(defaultErrorMessage, 'Operation failed');
      if (typeof showAlert === 'function') {
        showAlert(message);
      }
    } finally {
      confirmEl.disabled = false;
    }
  });

  return {
    open: ({ title, bodyHtml, confirmText = 'Confirm', confirmClass = 'btn-primary', onConfirm }) => {
      titleEl.textContent = resolveText(title, '');
      bodyEl.innerHTML = resolveText(bodyHtml, '');
      confirmEl.textContent = resolveText(confirmText, 'Confirm');
      confirmEl.className = `btn ${resolveText(confirmClass, 'btn-primary')}`;
      submitHandler = typeof onConfirm === 'function' ? onConfirm : null;
      modal.show();
    },
  };
};
