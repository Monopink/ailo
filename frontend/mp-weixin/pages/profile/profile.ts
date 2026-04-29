import { createPageLayoutData, type PageLayoutData } from '../../templates/page-layout';
import { requireAuth } from '../../utils/auth-guard';
import { getLogger } from '../../utils/logger';
import { type ProfileViewModel } from '../../utils/profile-service';
import { type ScreenModel } from '../../services/pages/page-state';
import { createProfilePageService } from '../../services/pages/profile-service';
import { showAuthExpiredModalAndRelogin } from '../../utils/auth-expired-modal';
import { initTabBar } from '../../utils/tab-bar';
import { isNonEmptyString } from '../../utils/guards';
import { IS_PROD } from '../../utils/env';
import { BUILD_INFO, formatBuildInfoText } from '../../utils/build-info';
import type { InviteBindingState } from '../../utils/invite-binding-service';
import authService from '../../utils/auth-service';
import { canUseInviteCapability } from '../../utils/access-capability';

const logger = getLogger('Profile');
const AUTO_RETRY_DELAYS_MS = [1200, 2600, 5200] as const;
type AuthGuardPage = WechatMiniprogram.Page.Instance<
  Record<string, unknown>,
  Record<string, unknown>
>;

interface ProfilePageData extends Record<string, unknown> {
  pageLayoutData: PageLayoutData;
  profile: ProfileViewModel | null;
  inviteBindingState: InviteBindingState;
  showInviteBindEntry: boolean;
  canUseInvite: boolean;
  showBuildInfo: boolean;
  buildInfoText: string;
}

interface ProfilePageCustom {
  profilePageService: ReturnType<typeof createProfilePageService>;
  _autoRetryTimer: ReturnType<typeof setTimeout> | null;
  _autoRetryAttempt: number;
  applyScreenModel(screenModel: ScreenModel): void;
  clearAutoRetryTimer(): void;
  scheduleAutoRetryLoad(): void;
  loadProfile(options?: { forceRefreshBinding?: boolean }): Promise<void>;
  ensureInviteAvailable(): boolean;
  navigateToProfileDetail(): void;
  navigateToInviteBind(): void;
  navigateToInviteShare(): void;
  navigateToAccountSecurity(): void;
  navigateToAbout(): void;
  onAvatarRenderSuccess(
    event: WechatMiniprogram.CustomEvent<WechatMiniprogram.GeneralCallbackResult>
  ): void;
  onAvatarRenderError(
    event: WechatMiniprogram.CustomEvent<WechatMiniprogram.GeneralCallbackResult>
  ): void;
  probeAvatarUrl(url: string): void;
  onUnload(): void;
}

const buildPageLayoutScreenModelPayload = (screenModel: ScreenModel): Record<string, unknown> => ({
  'pageLayoutData.screenModel': screenModel,
});

Page<ProfilePageData, ProfilePageCustom>({
  data: {
    pageLayoutData: createPageLayoutData({
      screenModel: {
        screenState: 'ready',
        contentVariant: 'data',
        refreshState: 'idle',
      },
      emptyMessage: '暂未获取到个人信息',
      hasFooter: true,
    }),
    profile: null,
    inviteBindingState: 'unknown',
    showInviteBindEntry: true,
    canUseInvite: true,
    showBuildInfo: !IS_PROD,
    buildInfoText: formatBuildInfoText(BUILD_INFO),
  },

  profilePageService: null as unknown as ReturnType<typeof createProfilePageService>,
  _autoRetryTimer: null,
  _autoRetryAttempt: 0,

  applyScreenModel(screenModel: ScreenModel) {
    this.setData(buildPageLayoutScreenModelPayload(screenModel));
  },

  clearAutoRetryTimer() {
    if (this._autoRetryTimer !== null) {
      clearTimeout(this._autoRetryTimer);
      this._autoRetryTimer = null;
    }
  },

  scheduleAutoRetryLoad() {
    if (this._autoRetryTimer !== null) {
      return;
    }
    if (this._autoRetryAttempt >= AUTO_RETRY_DELAYS_MS.length) {
      return;
    }

    const delay = AUTO_RETRY_DELAYS_MS[this._autoRetryAttempt];
    this._autoRetryTimer = setTimeout(() => {
      this._autoRetryTimer = null;
      this._autoRetryAttempt += 1;
      void this.loadProfile();
    }, delay);
  },

  async onLoad() {
    logger.info('Profile page loaded');
    this.profilePageService = createProfilePageService();
    this._autoRetryAttempt = 0;
    this.clearAutoRetryTimer();
    const isAuth = await requireAuth(this as unknown as AuthGuardPage);
    if (!isAuth) {
      return;
    }

    const bootstrap = this.profilePageService.bootstrap();
    const canUseInvite = canUseInviteCapability(authService.getUserInfo());
    this.setData({
      profile: bootstrap.profile,
      inviteBindingState: bootstrap.inviteBindingState,
      showInviteBindEntry: canUseInvite && bootstrap.inviteBindingState !== 'bound',
      canUseInvite,
      ...buildPageLayoutScreenModelPayload(bootstrap.screenModel),
    });

    await this.loadProfile({ forceRefreshBinding: true });
  },

  async onShow() {
    initTabBar(this);
    const isAuth = await requireAuth(this as unknown as AuthGuardPage);
    if (!isAuth) {
      return;
    }

    const bootstrap = this.profilePageService.bootstrap();
    const canUseInvite = canUseInviteCapability(authService.getUserInfo());
    if (bootstrap.profile === null && this.data.profile === null) {
      void this.loadProfile({ forceRefreshBinding: true });
      return;
    }
    this.setData({
      profile: bootstrap.profile ?? this.data.profile,
      inviteBindingState: bootstrap.inviteBindingState,
      showInviteBindEntry: canUseInvite && bootstrap.inviteBindingState !== 'bound',
      canUseInvite,
      ...buildPageLayoutScreenModelPayload(bootstrap.screenModel),
    });
    void this.loadProfile({ forceRefreshBinding: true });
  },

  onHide() {
    this.clearAutoRetryTimer();
  },

  onUnload() {
    this.clearAutoRetryTimer();
    this.profilePageService.dispose();
  },

  async loadProfile(options: { forceRefreshBinding?: boolean } = {}) {
    this.applyScreenModel({
      ...this.data.pageLayoutData.screenModel,
      screenState: 'ready',
      contentVariant: 'data',
      refreshState: 'refreshing',
    });

    logger.info('Loading user profile');
    const result = await this.profilePageService.load(
      this.data.profile,
      this.data.inviteBindingState,
      options
    );
    if (result === null) {
      return;
    }
    if (result.authInvalid) {
      await showAuthExpiredModalAndRelogin();
      return;
    }
    const canUseInvite = canUseInviteCapability(authService.getUserInfo());

    this.setData({
      profile: result.profile,
      inviteBindingState: result.inviteBindingState,
      showInviteBindEntry: canUseInvite && result.inviteBindingState !== 'bound',
      canUseInvite,
      ...buildPageLayoutScreenModelPayload(result.screenModel),
    });

    if (result.profile !== null) {
      this.probeAvatarUrl(result.profile.displayAvatar);
    }

    if (result.profile === null && result.screenModel.refreshState === 'degraded') {
      this.scheduleAutoRetryLoad();
      return;
    }

    this._autoRetryAttempt = 0;
    this.clearAutoRetryTimer();
    if (result.profile !== null) {
      logger.info('Profile loaded', { qiao_id: result.profile.qiao_id });
    }
  },

  navigateToProfileDetail() {
    void wx.navigateTo({
      url: '/pkg/profile-detail/profile-detail',
    });
  },

  navigateToAccountSecurity() {
    void wx.navigateTo({
      url: '/pkg/account-security/account-security',
    });
  },

  navigateToInviteBind() {
    if (!this.ensureInviteAvailable()) {
      return;
    }
    void wx.navigateTo({
      url: '/pages/invite-bind/invite-bind',
    });
  },

  navigateToInviteShare() {
    if (!this.ensureInviteAvailable()) {
      return;
    }
    void wx.navigateTo({
      url: '/pages/invite-share/invite-share',
    });
  },

  ensureInviteAvailable() {
    if (this.data.canUseInvite) {
      return true;
    }
    void wx.showToast({
      title: '该功能暂不可用',
      icon: 'none',
    });
    return false;
  },

  navigateToAbout() {
    void wx.navigateTo({
      url: '/pkg/about/about',
    });
  },

  onAvatarRenderSuccess(event) {
    logger.info('Avatar render success in native image', {
      detail: event.detail,
      avatarUrl: this.data.profile?.displayAvatar ?? '',
    });
  },

  onAvatarRenderError(event) {
    logger.error('Avatar render failed in native image', {
      detail: event.detail,
      avatarUrl: this.data.profile?.displayAvatar ?? '',
    });
  },

  probeAvatarUrl(url: string) {
    if (!isNonEmptyString(url)) {
      logger.warn('Avatar probe skipped: empty URL');
      return;
    }

    logger.info('Avatar probe start', { url });
    wx.getImageInfo({
      src: url,
      success: (result) => {
        logger.info('Avatar probe success', {
          url,
          width: result.width,
          height: result.height,
          type: result.type,
          path: result.path,
        });
      },
      fail: (error) => {
        logger.error('Avatar probe failed', {
          url,
          error,
        });
      },
    });
  },
});
