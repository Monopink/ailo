const resolveMessage = (value, fallback) => {
  if (typeof value === 'string' && value.trim() !== '') {
    return value.trim();
  }
  return fallback;
};

const ensureContainer = (containerId) => {
  const existing = document.getElementById(containerId);
  if (existing instanceof HTMLElement) {
    return existing;
  }

  const container = document.createElement('div');
  container.id = containerId;
  container.className = 'position-fixed top-0 end-0 p-3';
  container.style.zIndex = '1080';
  document.body.appendChild(container);
  return container;
};

export const createPageFeedback = ({ containerId = 'ailo-page-feedback-container', defaultAutoHideMs = 2600 } = {}) => {
  const container = ensureContainer(containerId);

  const show = ({ message, tone = 'danger', autoHideMs = defaultAutoHideMs }) => {
    const alertEl = document.createElement('div');
    alertEl.className = `alert alert-${tone} alert-dismissible fade show mb-2`;
    alertEl.setAttribute('role', 'alert');
    const textEl = document.createElement('span');
    textEl.textContent = resolveMessage(message, '');
    const closeEl = document.createElement('button');
    closeEl.type = 'button';
    closeEl.className = 'btn-close';
    closeEl.setAttribute('data-bs-dismiss', 'alert');
    closeEl.setAttribute('aria-label', 'Close');
    alertEl.appendChild(textEl);
    alertEl.appendChild(closeEl);
    container.appendChild(alertEl);
    if (Number.isFinite(autoHideMs) && autoHideMs > 0) {
      window.setTimeout(() => {
        if (alertEl.isConnected) {
          alertEl.remove();
        }
      }, autoHideMs);
    }
  };

  return {
    error: (message) => show({ message, tone: 'danger' }),
    success: (message) => show({ message, tone: 'success' }),
    info: (message) => show({ message, tone: 'secondary' }),
  };
};
