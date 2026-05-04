import { createPageLayoutData, type PageLayoutData } from '../../templates/page-layout';
import authService from '../../utils/auth-service';
import { getLogger } from '../../utils/logger';
import { ASSET_CONFIG, OFFICIAL_ACCOUNT_CONFIG } from '../../utils/config';
import { reportRuntimeObservation, shouldAllowPreviewAccess } from '../../utils/runtime-segment';

const ABOUT_CONTACT_US_ENTRY_SOURCE = 'about_contact_us';
const FAIL_ERR_MSG_MAX_LENGTH = 200;

const logger = getLogger('About');
const USER_AGREEMENT_PAGE_KEY = 'user_agreement';
const PRIVACY_POLICY_PAGE_KEY = 'privacy_policy';

interface AboutPageData extends Record<string, unknown> {
  pageLayoutData: PageLayoutData;
  previewFallbackEnabled: boolean;
  officialAccountFallbackVisible: boolean;
  officialAccountQrCodeUrl: string;
  officialAccountUsername: string;
  officialAccountFallbackConfirmBtn: Record<string, unknown>;
  officialAccountFallbackCancelBtn: Record<string, unknown>;
}

interface AboutPageCustom {
  navigateToUserAgreement(): void;
  navigateToPrivacyPolicy(): void;
  navigateToContactUs(): void;
  handleOfficialAccountFallbackConfirm(): void;
  handleOfficialAccountFallbackCancel(): void;
  handleOfficialAccountFallbackClose(): void;
  showOfficialAccountFallback(options: {
    reason: 'can_i_use_false' | 'api_fail';
    errMsg?: string;
  }): void;
  tryOpenOfficialAccountProfile(): Promise<{ ok: boolean; errMsg: string }>;
  navigateToContactUsInternal(): Promise<void>;
  handleOfficialAccountFallbackConfirmInternal(): Promise<void>;
}

Page<AboutPageData, AboutPageCustom>({
  data: {
    pageLayoutData: createPageLayoutData({
      screenModel: {
        screenState: 'ready',
        contentVariant: 'data',
        refreshState: 'idle',
      },
      hasFooter: false,
    }),
    previewFallbackEnabled: false,
    officialAccountFallbackVisible: false,
    officialAccountQrCodeUrl: ASSET_CONFIG.officialAccountQrCodeUrl,
    officialAccountUsername: OFFICIAL_ACCOUNT_CONFIG.username,
    officialAccountFallbackConfirmBtn: {
      content: '复制去搜一搜',
      variant: 'base',
      theme: 'primary',
    },
    officialAccountFallbackCancelBtn: {
      content: '关闭',
      variant: 'base',
      theme: 'default',
    },
  },

  onLoad(options: Record<string, string | undefined>) {
    const previewFlag = options.previewMode === '1';
    const previewFallbackEnabled =
      previewFlag && shouldAllowPreviewAccess() && !authService.isAuthenticated();
    this.setData({ previewFallbackEnabled });
    logger.info('About page loaded');
  },

  navigateToUserAgreement() {
    const previewFallbackQuery = this.data.previewFallbackEnabled ? '&previewFallback=1' : '';
    void wx.navigateTo({
      url: `/pkg/app-page/app-page?pageKey=${USER_AGREEMENT_PAGE_KEY}${previewFallbackQuery}`,
    });
  },

  navigateToPrivacyPolicy() {
    const previewFallbackQuery = this.data.previewFallbackEnabled ? '&previewFallback=1' : '';
    void wx.navigateTo({
      url: `/pkg/app-page/app-page?pageKey=${PRIVACY_POLICY_PAGE_KEY}${previewFallbackQuery}`,
    });
  },

  async tryOpenOfficialAccountProfile(): Promise<{ ok: boolean; errMsg: string }> {
    if (typeof wx.canIUse !== 'function' || !wx.canIUse('wx.openOfficialAccountProfile')) {
      return { ok: false, errMsg: 'canIUse failed' };
    }

    const originalId = OFFICIAL_ACCOUNT_CONFIG.originalId.trim();
    if (originalId === '') {
      logger.error('Official account originalId is not configured');
      return { ok: false, errMsg: 'originalId not configured' };
    }

    let lastErrMsg = '';
    try {
      const wxApi = wx as unknown as {
        openOfficialAccountProfile: (options: {
          username: string;
          success?: () => void;
          fail?: (res: { errMsg?: string }) => void;
        }) => void;
      };

      if (typeof wxApi.openOfficialAccountProfile !== 'function') {
        return { ok: false, errMsg: 'openOfficialAccountProfile is unavailable' };
      }

      await new Promise<void>((resolve, reject) => {
        wxApi.openOfficialAccountProfile({
          username: originalId,
          success: () => resolve(),
          fail: (res) => {
            lastErrMsg = typeof res.errMsg === 'string' ? res.errMsg : '';
            reject(new Error(lastErrMsg !== '' ? lastErrMsg : 'openOfficialAccountProfile failed'));
          },
        });
      });
      return { ok: true, errMsg: '' };
    } catch (error) {
      const errMsg = error instanceof Error ? error.message : lastErrMsg;
      logger.warn('openOfficialAccountProfile failed', { errMsg });
      return { ok: false, errMsg };
    }
  },

  showOfficialAccountFallback(options) {
    const rawErrMsg = typeof options.errMsg === 'string' ? options.errMsg : '';
    const failErrMsg =
      rawErrMsg.length > FAIL_ERR_MSG_MAX_LENGTH
        ? rawErrMsg.slice(0, FAIL_ERR_MSG_MAX_LENGTH)
        : rawErrMsg;

    void reportRuntimeObservation({
      eventName: 'official_account_follow_fallback_shown',
      pagePath: '/pkg/about/about',
      entrySource: ABOUT_CONTACT_US_ENTRY_SOURCE,
      eventPayload: {
        reason: options.reason,
        fail_err_msg: failErrMsg,
      },
    });

    this.setData({ officialAccountFallbackVisible: true });
  },

  navigateToContactUs() {
    void this.navigateToContactUsInternal();
  },

  async navigateToContactUsInternal() {
    void reportRuntimeObservation({
      eventName: 'official_account_follow_attempt',
      pagePath: '/pkg/about/about',
      entrySource: ABOUT_CONTACT_US_ENTRY_SOURCE,
      eventPayload: {
        method: 'open_profile',
        can_i_use_open_profile:
          typeof wx.canIUse === 'function' ? wx.canIUse('wx.openOfficialAccountProfile') : false,
      },
    });

    const canOpen =
      typeof wx.canIUse === 'function' && wx.canIUse('wx.openOfficialAccountProfile') === true;
    if (!canOpen) {
      this.showOfficialAccountFallback({ reason: 'can_i_use_false' });
      return;
    }

    const result = await this.tryOpenOfficialAccountProfile();
    if (!result.ok) {
      this.showOfficialAccountFallback({
        reason: 'api_fail',
        errMsg: result.errMsg !== '' ? result.errMsg : 'openOfficialAccountProfile failed',
      });
    }
  },

  handleOfficialAccountFallbackConfirm() {
    void this.handleOfficialAccountFallbackConfirmInternal();
  },

  async handleOfficialAccountFallbackConfirmInternal() {
    const username = OFFICIAL_ACCOUNT_CONFIG.username.trim();
    if (username === '') {
      void wx.showToast({ title: '系统错误', icon: 'none' });
      return;
    }
    try {
      await wx.setClipboardData({ data: username });
      this.setData({ officialAccountFallbackVisible: false });
    } catch (error) {
      logger.warn('setClipboardData failed', {
        errMsg: error instanceof Error ? error.message : '',
      });
    }
  },

  handleOfficialAccountFallbackCancel() {
    this.setData({ officialAccountFallbackVisible: false });
  },

  handleOfficialAccountFallbackClose() {
    this.setData({ officialAccountFallbackVisible: false });
  },
});
