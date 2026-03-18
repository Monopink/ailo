let authModalPromise: Promise<void> | null = null;

const showAuthModal = async (): Promise<void> =>
  await new Promise((resolve) => {
    void wx.showModal({
      title: '提示',
      content: '登录状态已失效，请重新登录',
      showCancel: false,
      confirmText: '去登录',
      complete: () => resolve(),
    });
  });

export const showAuthExpiredModalAndRelogin = async (): Promise<void> => {
  if (authModalPromise !== null) {
    return await authModalPromise;
  }

  authModalPromise = (async () => {
    try {
      await showAuthModal();
      void wx.reLaunch({ url: '/pages/login/login' });
    } finally {
      authModalPromise = null;
    }
  })();

  return await authModalPromise;
};
