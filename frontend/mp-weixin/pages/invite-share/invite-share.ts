import { createPageLayoutData, type PageLayoutData } from '../../templates/page-layout';
import { createInviteShareService } from '../../services/pages/invite-share-service';
import { classifyError } from '../../utils/error-classifier';
import { showAuthExpiredModalAndRelogin } from '../../utils/auth-expired-modal';
import { requireAuth } from '../../utils/auth-guard';
import { getLogger } from '../../utils/logger';

type AuthGuardPage = WechatMiniprogram.Page.Instance<
  Record<string, unknown>,
  Record<string, unknown>
>;

const logger = getLogger('InviteShare');

interface InviteSharePageData extends Record<string, unknown> {
  pageLayoutData: PageLayoutData;
  myCode: string;
  shareText: string;
  shareTitle: string;
  sharePath: string;
  shareImageUrl: string;
  shareSlotCode: string;
  shareSlotVersion: number;
  successInviteCount: number;
  maxInviteCount: number | null;
  rewardContactLimitPerInvite: number;
  maxRewardContactLimitTotal: number | null;
  rewardedContactLimitTotal: number;
  loading: boolean;
}

interface InviteSharePageCustom {
  invitationService: ReturnType<typeof createInviteShareService>;
  loadData(): Promise<void>;
  handleCopyCode(): Promise<void>;
  handleCopyCommand(): Promise<void>;
  onShareAppMessage(): WechatMiniprogram.Page.ICustomShareContent;
  onUnload(): void;
}

const buildScreenModelPayload = (
  screenState: 'booting' | 'ready',
  contentVariant: 'data' | 'empty' | 'blank',
  refreshState: 'idle' | 'refreshing' | 'degraded'
): Record<string, unknown> => ({
  'pageLayoutData.screenModel': {
    screenState,
    contentVariant,
    refreshState,
  },
});

Page<InviteSharePageData, InviteSharePageCustom>({
  data: {
    pageLayoutData: createPageLayoutData({
      screenModel: {
        screenState: 'ready',
        contentVariant: 'data',
        refreshState: 'idle',
      },
      hasFooter: true,
    }),
    myCode: '',
    shareText: '',
    shareTitle: '',
    sharePath: '',
    shareImageUrl: '',
    shareSlotCode: '',
    shareSlotVersion: 0,
    successInviteCount: 0,
    maxInviteCount: null,
    rewardContactLimitPerInvite: 0,
    maxRewardContactLimitTotal: null,
    rewardedContactLimitTotal: 0,
    loading: false,
  },

  invitationService: null as unknown as ReturnType<typeof createInviteShareService>,

  async onLoad() {
    this.invitationService = createInviteShareService();
    const isAuth = await requireAuth(this as unknown as AuthGuardPage);
    if (!isAuth) {
      return;
    }
    void wx.showShareMenu({ menus: ['shareAppMessage'] });
    await this.loadData();
  },

  onUnload() {
    this.invitationService.dispose();
  },

  async loadData() {
    this.setData({ loading: true, ...buildScreenModelPayload('ready', 'data', 'refreshing') });
    try {
      const shareResponse = await this.invitationService.getInviteShareText();
      if (shareResponse === null) {
        return;
      }
      let successInviteCount = 0;
      let maxInviteCount: number | null = null;
      let rewardContactLimitPerInvite = 0;
      let maxRewardContactLimitTotal: number | null = null;
      let rewardedContactLimitTotal = 0;
      try {
        const statsResponse = await this.invitationService.getInviteStats();
        if (statsResponse !== null) {
          successInviteCount = statsResponse.success_invite_count;
          maxInviteCount = statsResponse.max_invite_count;
          rewardContactLimitPerInvite = statsResponse.reward_contact_limit_per_invite;
          maxRewardContactLimitTotal = statsResponse.max_reward_contact_limit_total;
          rewardedContactLimitTotal = statsResponse.rewarded_contact_limit_total;
        }
      } catch (error) {
        logger.warn('Load invite stats failed, fallback to zero', { error });
      }
      this.setData({
        myCode: shareResponse.code,
        shareText: shareResponse.text,
        shareTitle: shareResponse.share_card.title,
        sharePath: shareResponse.share_card.path,
        shareImageUrl: shareResponse.share_card.image_url,
        shareSlotCode: shareResponse.share_card.slot_code,
        shareSlotVersion: shareResponse.share_card.version,
        successInviteCount,
        maxInviteCount,
        rewardContactLimitPerInvite,
        maxRewardContactLimitTotal,
        rewardedContactLimitTotal,
        ...buildScreenModelPayload('ready', 'data', 'idle'),
      });
    } catch (error) {
      const semantics = classifyError(error);
      if (semantics.reason === 'auth-invalid') {
        await showAuthExpiredModalAndRelogin();
        return;
      }
      logger.error('Load invite share page failed', { error });
      this.setData(buildScreenModelPayload('ready', 'data', 'degraded'));
      void wx.showToast({ title: '加载失败，请稍后重试', icon: 'none' });
    } finally {
      this.setData({ loading: false });
    }
  },

  async handleCopyCode() {
    const inviteCode = this.data.myCode;
    if (inviteCode.trim() === '') {
      void wx.showToast({ title: '邀请码为空，请先刷新', icon: 'none' });
      return;
    }
    try {
      await wx.setClipboardData({ data: inviteCode });
      void this.invitationService
        .trackInviteEvent('copy_command', {
          code: inviteCode,
          payload: { target: 'code', length: inviteCode.length },
        })
        .catch((error: unknown) => {
          logger.debug('Track copy invite code event failed', { error });
        });
      void wx.showToast({ title: '已复制邀请码', icon: 'success' });
    } catch (error) {
      logger.error('Copy invite code failed', { error });
      void wx.showToast({ title: '复制失败，请重试', icon: 'none' });
    }
  },

  async handleCopyCommand() {
    try {
      const shareResponse = await this.invitationService.getInviteShareText();
      if (shareResponse === null) {
        return;
      }
      const shareText = shareResponse.text;
      if (shareText.trim() === '') {
        void wx.showToast({ title: '口令为空，请稍后重试', icon: 'none' });
        return;
      }

      this.setData({
        myCode: shareResponse.code,
        shareText,
        shareTitle: shareResponse.share_card.title,
        sharePath: shareResponse.share_card.path,
        shareImageUrl: shareResponse.share_card.image_url,
        shareSlotCode: shareResponse.share_card.slot_code,
        shareSlotVersion: shareResponse.share_card.version,
      });

      await wx.setClipboardData({ data: shareText });
      void this.invitationService
        .trackInviteEvent('copy_command', {
          code: shareResponse.code,
          payload: { target: 'command', length: shareText.length },
        })
        .catch((error: unknown) => {
          logger.debug('Track copy_command invite event failed', { error });
        });

      await wx.showModal({
        title: '邀请口令已复制',
        content: `口令已复制：【${shareText}】\n\n请把口令发送给好友或群聊，对方打开并完成绑定后即可生效。`,
        showCancel: false,
        confirmText: '我知道了',
      });
    } catch (error) {
      logger.error('Copy invite share text failed', { error });
      void wx.showToast({ title: '复制失败，请重试', icon: 'none' });
    }
  },

  onShareAppMessage() {
    const sharePayload: Record<string, unknown> = {};
    if (this.data.shareSlotCode.trim() !== '') {
      sharePayload.slot_code = this.data.shareSlotCode;
    }
    if (this.data.shareSlotVersion > 0) {
      sharePayload.slot_version = this.data.shareSlotVersion;
    }

    void this.invitationService
      .trackInviteEvent('share_wechat', {
        code: this.data.myCode,
        payload: Object.keys(sharePayload).length > 0 ? sharePayload : undefined,
      })
      .catch((error: unknown) => {
        logger.debug('Track share_wechat invite event failed', { error });
      });

    const response: WechatMiniprogram.Page.ICustomShareContent = {
      title: this.data.shareTitle,
      path: this.data.sharePath,
    };
    response.imageUrl = this.data.shareImageUrl;

    return response;
  },
});
