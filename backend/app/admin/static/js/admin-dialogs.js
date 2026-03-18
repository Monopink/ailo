(function () {
  const modalId = 'qiao-admin-confirm-modal';
  const titleId = 'qiao-admin-confirm-title';
  const messageId = 'qiao-admin-confirm-message';
  const cancelId = 'qiao-admin-confirm-cancel';
  const confirmId = 'qiao-admin-confirm-confirm';

  let modalInstance = null;

  function getModalElement() {
    return document.getElementById(modalId);
  }

  function ensureModal() {
    const modalEl = getModalElement();
    if (!modalEl || !window.bootstrap?.Modal) {
      return null;
    }
    if (!modalInstance) {
      modalInstance = new window.bootstrap.Modal(modalEl);
    }
    return modalInstance;
  }

  function getElements() {
    const modalEl = getModalElement();
    if (!modalEl) {
      return null;
    }
    return {
      modalEl,
      titleEl: document.getElementById(titleId),
      messageEl: document.getElementById(messageId),
      cancelEl: document.getElementById(cancelId),
      confirmEl: document.getElementById(confirmId),
      closeEl: modalEl.querySelector('.btn-close'),
    };
  }

  function htmlToText(value) {
    const temp = document.createElement('div');
    temp.innerHTML = value;
    return temp.textContent || temp.innerText || '';
  }

  function normalizeMessage(value) {
    return htmlToText(String(value || '').replace(/<br\s*\/?>/gi, '\n'));
  }

  function fallbackConfirm(options) {
    const message = options.message ? normalizeMessage(options.message) : '确定执行该操作？';
    return Promise.resolve(window.confirm(message));
  }

  function confirm(options = {}) {
    const settings = {
      title: '确认',
      message: '确定执行该操作？',
      confirmText: '确认',
      cancelText: '取消',
      confirmButtonClass: 'btn btn-primary',
      ...options,
    };

    const elements = getElements();
    const modal = ensureModal();
    if (!elements || !modal) {
      return fallbackConfirm(settings);
    }

    const { modalEl, titleEl, messageEl, cancelEl, confirmEl, closeEl } = elements;

    if (titleEl) {
      titleEl.textContent = settings.title;
    }
    if (messageEl) {
      messageEl.textContent = normalizeMessage(settings.message);
    }
    if (cancelEl) {
      cancelEl.textContent = settings.cancelText;
    }
    if (confirmEl) {
      confirmEl.textContent = settings.confirmText;
      confirmEl.className = settings.confirmButtonClass;
    }

    return new Promise((resolve) => {
      let resolved = false;

      const cleanup = () => {
        confirmEl?.removeEventListener('click', onConfirm);
        cancelEl?.removeEventListener('click', onCancel);
        closeEl?.removeEventListener('click', onCancel);
        modalEl.removeEventListener('hidden.bs.modal', onHidden);
      };

      const finish = (result) => {
        if (resolved) {
          return;
        }
        resolved = true;
        cleanup();
        resolve(result);
      };

      const onConfirm = () => {
        modal.hide();
        finish(true);
      };

      const onCancel = () => {
        modal.hide();
        finish(false);
      };

      const onHidden = () => {
        finish(false);
      };

      confirmEl?.addEventListener('click', onConfirm, { once: true });
      cancelEl?.addEventListener('click', onCancel, { once: true });
      closeEl?.addEventListener('click', onCancel, { once: true });
      modalEl.addEventListener('hidden.bs.modal', onHidden, { once: true });

      modal.show();
    });
  }

  window.qiaoAdminDialogs = Object.freeze({
    confirm,
  });
})();
