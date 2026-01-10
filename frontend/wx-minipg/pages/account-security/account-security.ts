import { createPageLayoutData, type PageLayoutData } from '../../templates/page-layout';
import { requireAuth } from '../../utils/auth-guard';
import authService from '../../utils/auth-service';
import accountService, { type AccountViewModel } from '../../utils/account-service';
import { getLogger } from '../../utils/logger';
import { isNonEmptyString } from '../../utils/guards';

const logger = getLogger('AccountSecurity');

type AuthGuardPage = WechatMiniprogram.Page.Instance<
  Record<string, unknown>,
  Record<string, unknown>
>;

interface AccountSecurityPageData extends Record<string, unknown> {
  pageLayoutData: PageLayoutData;
  phoneMasked: string;
  account: AccountViewModel | null;
  isLogoutProcessing: boolean;
  phoneReauthLoading: boolean;
}

interface AccountSecurityPageCustom {
  loadAccountInfo(): Promise<void>;
  handlePhoneReauthorize(event: WechatMiniprogram.ButtonGetPhoneNumber): Promise<void>;
  handleLogout(): Promise<void>;
  onRetry(): void;
}

const toError = (error: unknown): Error => {
  if (error instanceof Error) {
    return error;
  }
  if (typeof error === 'string') {
    return new Error(error);
  }
  try {
    return new Error(JSON.stringify(error));
  } catch {
    return new Error('Unknown error');
  }
};

const showModal = async (
  options: WechatMiniprogram.ShowModalOption
): Promise<WechatMiniprogram.ShowModalSuccessCallbackResult> =>
  await new Promise((resolve, reject) => {
    wx.showModal({
      ...options,
      success: resolve,
      fail: reject,
    });
  });

Page<AccountSecurityPageData, AccountSecurityPageCustom>({
  data: {
    pageLayoutData: createPageLayoutData({
      isLoading: true,
      emptyMessage: '暂无账号信息',
      hasFooter: false,
    }),
    phoneMasked: '',
    account: null,
    isLogoutProcessing: false,
    phoneReauthLoading: false,
  },

  async onLoad() {
    logger.info('Account security page loaded');
    const isAuth = await requireAuth(this as unknown as AuthGuardPage);
    if (!isAuth) {
      return;
    }

    await this.loadAccountInfo();
  },

  async loadAccountInfo() {
    try {
      this.setData({
        'pageLayoutData.isLoading': true,
        'pageLayoutData.hasError': false,
        'pageLayoutData.errorMessage': '',
      });

      logger.info('Loading account info');
      const account = await accountService.loadAccountInfo();

      this.setData({
        account,
        phoneMasked: account.displayPhone,
        'pageLayoutData.isLoading': false,
        'pageLayoutData.isEmpty': false,
      });

      logger.info('Account info loaded');
    } catch (error) {
      const err = toError(error);
      logger.error('Load account info failed', { error: err.message });

      this.setData({
        account: null,
        phoneMasked: '',
        'pageLayoutData.isLoading': false,
        'pageLayoutData.hasError': true,
        'pageLayoutData.errorMessage': '加载失败，请稍后再试',
      });

      void wx.showToast({
        title: '加载失败',
        icon: 'none',
      });
    }
  },

  async handlePhoneReauthorize(event: WechatMiniprogram.ButtonGetPhoneNumber) {
    if (this.data.phoneReauthLoading) {
      return;
    }

    if (event.detail.errMsg !== 'getPhoneNumber:ok') {
      logger.warn('Phone reauthorization rejected', { errMsg: event.detail.errMsg });
      void wx.showToast({
        title: '需要授权手机号才能更新',
        icon: 'none',
      });
      return;
    }

    const phoneCode = event.detail.code;
    this.setData({ phoneReauthLoading: true });

    try {
      const { code: loginCode } = await wx.login();
      if (!isNonEmptyString(loginCode)) {
        throw new Error('无法获取登录凭证');
      }

      const updatedAccount = await accountService.refreshPhoneNumber(phoneCode, loginCode);

      void wx.showToast({
        title: '手机号已更新',
        icon: 'success',
      });

      this.setData({
        account: updatedAccount,
        phoneMasked: updatedAccount.displayPhone,
      });
    } catch (error) {
      const err = toError(error);
      logger.error('Phone reauthorization failed', { error: err.message });
      const toastTitle = isNonEmptyString(err.message) ? err.message : '更新失败，请稍后再试';
      void wx.showToast({
        title: toastTitle,
        icon: 'none',
      });
    } finally {
      this.setData({ phoneReauthLoading: false });
    }
  },

  async handleLogout() {
    if (this.data.isLogoutProcessing) {
      return;
    }

    const result = await showModal({
      title: '退出登录',
      content: '确定要退出当前账号吗？',
      confirmText: '退出',
      cancelText: '取消',
    });

    if (!result.confirm) {
      return;
    }

    this.setData({ isLogoutProcessing: true });

    try {
      void wx.showLoading({
        title: '正在退出',
        mask: true,
      });

      await authService.logout();

      const app = getApp<AppInstance>();
      const messageService = app.getMessageService();
      if (messageService !== null) {
        await messageService.disconnect();
        app.globalData.messageService = null;
      }

      void wx.reLaunch({
        url: '/pages/login/login',
      });
    } catch (error) {
      const err = toError(error);
      logger.error('Logout failed', { error: err.message });

      void wx.showToast({
        title: '退出失败，请稍后重试',
        icon: 'none',
      });
    } finally {
      this.setData({ isLogoutProcessing: false });
      void wx.hideLoading();
    }
  },

  onRetry() {
    void this.loadAccountInfo();
  },
});
