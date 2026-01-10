import { createPageLayoutData, type PageLayoutData } from '../../templates/page-layout';
import { requireAuth } from '../../utils/auth-guard';
import { getLogger } from '../../utils/logger';
import profileService, { type ProfileViewModel } from '../../utils/profile-service';
import { initTabBar } from '../../utils/tab-bar';

const logger = getLogger('Profile');
type AuthGuardPage = WechatMiniprogram.Page.Instance<
  Record<string, unknown>,
  Record<string, unknown>
>;

interface ProfilePageData extends Record<string, unknown> {
  pageLayoutData: PageLayoutData;
  profile: ProfileViewModel | null;
}

interface ProfilePageCustom {
  loadProfile(): Promise<void>;
  navigateToProfileDetail(): void;
  navigateToAccountSecurity(): void;
  navigateToAbout(): void;
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

Page<ProfilePageData, ProfilePageCustom>({
  data: {
    pageLayoutData: createPageLayoutData({
      isLoading: true,
      emptyMessage: '暂未获取到个人信息',
      hasFooter: true,
    }),
    profile: null,
  },

  async onLoad() {
    logger.info('Profile page loaded');
    const isAuth = await requireAuth(this as unknown as AuthGuardPage);
    if (!isAuth) {
      return;
    }

    await this.loadProfile();
  },

  async onShow() {
    const isAuth = await requireAuth(this as unknown as AuthGuardPage);
    if (!isAuth) {
      return;
    }

    initTabBar(this);

    await this.loadProfile();
  },

  async loadProfile() {
    try {
      this.setData({
        'pageLayoutData.isLoading': true,
        'pageLayoutData.hasError': false,
        'pageLayoutData.errorMessage': '',
      });

      logger.info('Loading user profile');
      const profile = await profileService.loadProfile();

      this.setData({
        profile,
        'pageLayoutData.isLoading': false,
        'pageLayoutData.isEmpty': false,
      });

      logger.info('Profile loaded', { qiao_id: profile.qiao_id });
    } catch (error) {
      const err = toError(error);
      logger.error('Load profile failed', { error: err.message });

      this.setData({
        profile: null,
        'pageLayoutData.isLoading': false,
        'pageLayoutData.hasError': true,
        'pageLayoutData.errorMessage': '加载失败,请稍后再试',
      });

      void wx.showToast({
        title: '加载失败',
        icon: 'none',
      });
    }
  },

  navigateToProfileDetail() {
    void wx.navigateTo({
      url: '/pages/profile-detail/profile-detail',
    });
  },

  navigateToAccountSecurity() {
    void wx.navigateTo({
      url: '/pages/account-security/account-security',
    });
  },

  navigateToAbout() {
    void wx.navigateTo({
      url: '/pages/about/about',
    });
  },

  onRetry() {
    void this.loadProfile();
  },
});
