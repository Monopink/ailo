import { get } from '../../utils/api';
import { requireAuth } from '../../utils/auth-guard';
import authService from '../../utils/auth-service';
import { getAvatarUrl } from '../../utils/avatar';
import { getLogger } from '../../utils/logger';

const logger = getLogger('Profile');

type AnyObject = WechatMiniprogram.IAnyObject;
type AuthGuardPage = WechatMiniprogram.Page.Instance<
  Record<string, unknown>,
  Record<string, unknown>
>;

interface UserProfile extends AnyObject {
  qiao_id?: string;
  avatar_url?: string | null;
  custom_avatar_url?: string | null;
  gender?: number | null;
}

interface ProfilePageData extends Record<string, unknown> {
  loading: boolean;
  profile: UserProfile | null;
  error: string | null;
}

interface ProfilePageCustom {
  loadProfile(): Promise<void>;
  navigateToProfileDetail(): void;
  handleLogout(): Promise<void>;
  getGenderText(gender?: number | null): string;
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

Page<ProfilePageData, ProfilePageCustom>({
  data: {
    loading: true,
    profile: null,
    error: null,
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
    await this.loadProfile();
  },

  async loadProfile() {
    try {
      this.setData({
        loading: true,
        error: null,
      });

      logger.info('Loading user profile');
      const profile = await get<UserProfile>('/user/profile');

      this.setData({
        profile: {
          ...profile,
          avatar_url: getAvatarUrl(profile?.avatar_url ?? ''),
        },
        loading: false,
      });

      logger.info('Profile loaded', { qiao_id: profile?.qiao_id });
    } catch (error) {
      const err = toError(error);
      logger.error('Load profile failed', { error: err.message });

      this.setData({
        error: '加载失败,请稍后再试',
        loading: false,
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

  async handleLogout() {
    try {
      const result = await showModal({
        title: '退出登录',
        content: '确定要退出当前账号吗？',
        confirmText: '退出',
        cancelText: '取消',
      });

      if (!result.confirm) {
        return;
      }

      void wx.showLoading({
        title: '正在退出',
        mask: true,
      });

      await authService.logout();

      const app = getApp<SaysAppInstance>();
      const messageService = app.getMessageService();
      if (messageService) {
        await messageService.disconnect();
        app.globalData.messageService = null;
      }

      void wx.hideLoading();

      void wx.reLaunch({
        url: '/pages/login/login',
      });
    } catch (error) {
      const err = toError(error);
      logger.error('Logout failed', { error: err.message });

      void wx.hideLoading();

      void wx.showToast({
        title: '退出失败，请稍后重试',
        icon: 'none',
      });
    }
  },

  getGenderText(gender) {
    const genderMap: Record<number, string> = {
      1: '男',
      2: '女',
      3: '其他',
      4: '未知',
    };
    return genderMap[Number(gender)] ?? '未设置';
  },
});
