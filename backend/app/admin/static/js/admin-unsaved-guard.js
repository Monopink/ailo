(function () {
  const defaultMessage = '当前编辑内容尚未保存，确认放弃并离开此页面吗？';

  function isModifiedClick(event) {
    return (
      event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey
    );
  }

  function isGuardableLink(anchor) {
    if (!anchor || anchor.hasAttribute('download')) {
      return false;
    }
    if (anchor.dataset.qiaoGuardIgnore === 'true') {
      return false;
    }
    const href = anchor.getAttribute('href');
    if (!href || href === '#' || href.startsWith('javascript:')) {
      return false;
    }
    if (anchor.target && anchor.target !== '_self') {
      return false;
    }
    try {
      const targetUrl = new window.URL(anchor.href, window.location.href);
      if (targetUrl.origin !== window.location.origin) {
        return false;
      }
      if (targetUrl.href === window.location.href) {
        return false;
      }
      return true;
    } catch {
      return false;
    }
  }

  function createUnsavedChangesGuard(config = {}) {
    const settings = {
      isDirty: () => false,
      message: defaultMessage,
      beforeUnloadMessage: '',
      shouldHandleLink: null,
      ...config,
    };

    let bypassNextNavigation = false;
    let disposed = false;

    async function confirmLeave(customMessage) {
      const dialogs = window.qiaoAdminDialogs;
      const message = customMessage || settings.message;
      if (!settings.isDirty()) {
        return true;
      }
      if (dialogs?.confirm) {
        return dialogs.confirm({
          title: '放弃编辑',
          message,
          confirmText: '放弃并离开',
          cancelText: '继续编辑',
          confirmButtonClass: 'btn btn-danger',
        });
      }
      return window.confirm(String(message).replace(/<br\s*\/?>/gi, '\n'));
    }

    function beforeUnloadHandler(event) {
      if (bypassNextNavigation || !settings.isDirty()) {
        return;
      }
      event.preventDefault();
      event.returnValue = settings.beforeUnloadMessage;
      return settings.beforeUnloadMessage;
    }

    async function clickHandler(event) {
      if (disposed || bypassNextNavigation || isModifiedClick(event)) {
        return;
      }
      const anchor = event.target.closest('a[href]');
      if (!anchor || !isGuardableLink(anchor)) {
        return;
      }
      if (typeof settings.shouldHandleLink === 'function' && !settings.shouldHandleLink(anchor, event)) {
        return;
      }
      if (!settings.isDirty()) {
        return;
      }
      event.preventDefault();
      const ok = await confirmLeave(anchor.dataset.qiaoGuardMessage);
      if (!ok) {
        return;
      }
      bypassNextNavigation = true;
      window.location.assign(anchor.href);
    }

    window.addEventListener('beforeunload', beforeUnloadHandler);
    document.addEventListener('click', clickHandler, true);

    return Object.freeze({
      async confirmLeave(customMessage) {
        return confirmLeave(customMessage);
      },
      bypassOnce() {
        bypassNextNavigation = true;
      },
      resetBypass() {
        bypassNextNavigation = false;
      },
      dispose() {
        disposed = true;
        window.removeEventListener('beforeunload', beforeUnloadHandler);
        document.removeEventListener('click', clickHandler, true);
      },
    });
  }

  window.qiaoUnsavedGuard = Object.freeze({
    create: createUnsavedChangesGuard,
  });
})();
