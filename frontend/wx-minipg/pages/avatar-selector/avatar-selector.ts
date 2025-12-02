import { put } from '../../utils/api';
import { getLogger } from '../../utils/logger';

const logger = getLogger('AvatarSelector');

const PRESET_AVATAR_IDS = ['1574', '2454', '3758'] as const;

interface AvatarItem {
  id: string;
  url: string;
  name: string;
}

interface AvatarSelectorPageData {
  loading: boolean;
  presetAvatars: AvatarItem[];
  currentAvatar: string;
  selectedAvatar: string;
  error: string | null;
}

type AvatarTapEvent = WechatMiniprogram.TouchEvent<
  WechatMiniprogram.IAnyObject,
  WechatMiniprogram.IAnyObject,
  { id?: string }
>;

interface AvatarSelectorPageCustom {
  loadPresetAvatars(): void;
  selectAvatar(event: AvatarTapEvent): void;
  confirmSelection(): Promise<void>;
  cancel(): void;
}

const buildAvatarItems = (): AvatarItem[] =>
  PRESET_AVATAR_IDS.map((id) => ({
    id: `assets://${id}`,
    url: `/assets/avatars/${id}.jpg`,
    name: id,
  }));

Page<AvatarSelectorPageData, AvatarSelectorPageCustom>({
  data: {
    loading: true,
    presetAvatars: [],
    currentAvatar: '',
    selectedAvatar: '',
    error: null,
  },

  onLoad(options) {
    logger.info('Avatar selector page loaded');
    const currentAvatar = options?.avatar ?? '';
    this.setData({ currentAvatar });
    this.loadPresetAvatars();
  },

  loadPresetAvatars() {
    logger.info('Loading preset avatars');
    const avatars = buildAvatarItems();
    this.setData({
      presetAvatars: avatars,
      loading: false,
    });
    logger.info('Preset avatars loaded', { count: avatars.length });
  },

  selectAvatar(event) {
    const avatarId = event.currentTarget.dataset.id;
    if (!avatarId) {
      return;
    }
    logger.info('Avatar selected', { avatarId });
    this.setData({ selectedAvatar: String(avatarId) });
  },

  async confirmSelection() {
    if (!this.data.selectedAvatar) {
      void wx.showToast({
        title: '请选择头像',
        icon: 'none',
      });
      return;
    }

    try {
      logger.info('Updating avatar', { avatar: this.data.selectedAvatar });
      await put('/user/profile', {
        avatar_url: this.data.selectedAvatar,
      });

      void wx.showToast({
        title: '头像已更新',
        icon: 'success',
      });

      setTimeout(() => {
        void wx.navigateBack();
      }, 1000);
    } catch (error) {
      logger.error('Update avatar failed', {
        error: error instanceof Error ? error.message : String(error),
      });

      void wx.showToast({
        title: '更新失败',
        icon: 'none',
      });
    }
  },

  cancel() {
    void wx.navigateBack();
  },
});
