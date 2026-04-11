import { createPageLayoutData, type PageLayoutData } from '../../templates/page-layout';
import { requireAuth } from '../../utils/auth-guard';
import authService from '../../utils/auth-service';
import { type AccountViewModel } from '../../utils/account-service';
import { getLogger } from '../../utils/logger';
import { normalizeError } from '../../utils/errors';
import { type ScreenModel } from '../../services/pages/page-state';
import { createAccountSecurityPageService } from '../../services/pages/account-security-service';
import { showAuthExpiredModalAndRelogin } from '../../utils/auth-expired-modal';
import { type MinorModeStatus } from '../../utils/minor-mode';

const logger = getLogger('AccountSecurity');

type AuthGuardPage = WechatMiniprogram.Page.Instance<
  Record<string, unknown>,
  Record<string, unknown>
>;

interface AccountSecurityPageData extends Record<string, unknown> {
  pageLayoutData: PageLayoutData;
  phoneMasked: string;
  account: AccountViewModel | null;
  minorModeStatus: MinorModeStatus | null;
  isLogoutProcessing: boolean;
}

interface AccountSecurityPageCustom {
  accountSecurityPageService: ReturnType<typeof createAccountSecurityPageService>;
  applyScreenModel(screenModel: ScreenModel): void;
  loadAccountInfo(): Promise<void>;
  openMinorModePage(): void;
  handleLogout(): Promise<void>;
}

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

const buildPageLayoutScreenModelPayload = (screenModel: ScreenModel): Record<string, unknown> => ({
  'pageLayoutData.screenModel': screenModel,
});

Page<AccountSecurityPageData, AccountSecurityPageCustom>({
  data: {
    pageLayoutData: createPageLayoutData({
      screenModel: {
        screenState: 'ready',
        contentVariant: 'data',
        refreshState: 'idle',
      },
      emptyMessage: '暂无账号信息',
      hasFooter: false,
    }),
    phoneMasked: '',
    account: null,
    minorModeStatus: null,
    isLogoutProcessing: false,
  },

  accountSecurityPageService: null as unknown as ReturnType<
    typeof createAccountSecurityPageService
  >,

  applyScreenModel(screenModel: ScreenModel) {
    this.setData(buildPageLayoutScreenModelPayload(screenModel));
  },

  async onLoad() {
    logger.info('Account security page loaded');
    this.accountSecurityPageService = createAccountSecurityPageService();
    const isAuth = await requireAuth(this as unknown as AuthGuardPage);
    if (!isAuth) {
      return;
    }

    await this.loadAccountInfo();
  },

  onShow() {
    // Non-realtime page: do not auto-reload on every show.
  },

  onUnload() {
    this.accountSecurityPageService.dispose();
  },

  async loadAccountInfo() {
    this.applyScreenModel({
      ...this.data.pageLayoutData.screenModel,
      screenState: 'ready',
      contentVariant: 'data',
      refreshState: 'refreshing',
    });

    logger.info('Loading account info');
    const result = await this.accountSecurityPageService.load(this.data.account);
    if (result === null) {
      return;
    }
    if (result.authInvalid) {
      await showAuthExpiredModalAndRelogin();
      return;
    }

    this.setData({
      account: result.account,
      phoneMasked: result.account?.displayPhone ?? '',
      minorModeStatus: result.minorModeStatus,
      ...buildPageLayoutScreenModelPayload(result.screenModel),
    });
  },

  openMinorModePage() {
    void wx.navigateTo({
      url: '/pages/minor-mode/minor-mode',
      events: {
        statusChanged: () => {
          void this.loadAccountInfo();
        },
      },
    });
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
        url: '/pages/login/login?source=logout',
      });
    } catch (error) {
      const err = normalizeError(error);
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
});
