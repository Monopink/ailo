import { createPageLayoutData, type PageLayoutData } from '../../templates/page-layout';
import { createInviteShareService } from '../../services/pages/invite-share-service';
import { classifyError } from '../../utils/error-classifier';
import { showAuthExpiredModalAndRelogin } from '../../utils/auth-expired-modal';
import { requireAuth } from '../../utils/auth-guard';
import { getLogger } from '../../utils/logger';
import authService from '../../utils/auth-service';
import { canUseInviteCapability } from '../../utils/access-capability';

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
  successInviteCount: number;
  maxInviteCount: number | null;
  inviterRewardContactDelta: number;
  inviteeRewardContactDelta: number;
  activityRewardHintText: string;
  stepRewardHintText: string;
  ruleRewardHintText: string;
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

const buildRewardHintText = (
  inviteeRewardContactDelta: number,
  inviterRewardContactDelta: number
): string => {
  if (inviteeRewardContactDelta === inviterRewardContactDelta) {
    return `每邀请1位用户，双方各增加 ${inviteeRewardContactDelta} 个联系人上限。`;
  }
  return `每邀请1位用户，你增加 ${inviterRewardContactDelta} 个联系人上限，对方增加 ${inviteeRewardContactDelta} 个联系人上限。`;
};

const buildRuleHintText = (
  inviteeRewardContactDelta: number,
  inviterRewardContactDelta: number
): string => {
  if (inviteeRewardContactDelta === inviterRewardContactDelta) {
    return `每次成功绑定后，邀请双方各增加 ${inviteeRewardContactDelta} 个联系人上限。`;
  }
  return `每次成功绑定后，你增加 ${inviterRewardContactDelta} 个联系人上限，对方增加 ${inviteeRewardContactDelta} 个联系人上限。`;
};

const navigateWhenInviteUnavailable = (): void => {
  void wx.showToast({ title: '该功能暂不可用', icon: 'none' });
  if (getCurrentPages().length > 1) {
    void wx.navigateBack();
    return;
  }
  void wx.switchTab({ url: '/pages/index/index' });
};

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
    successInviteCount: 0,
    maxInviteCount: null,
    inviterRewardContactDelta: 0,
    inviteeRewardContactDelta: 0,
    activityRewardHintText: '每邀请1位用户，可增加联系人上限。',
    stepRewardHintText: '绑定成功后，可增加联系人上限。',
    ruleRewardHintText: '每次成功绑定后，可增加联系人上限。',
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
    if (!canUseInviteCapability(authService.getUserInfo())) {
      navigateWhenInviteUnavailable();
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
      const [codeResponse, shareCardResponse, policyResponse, statsResponse] = await Promise.all([
        this.invitationService.getInviteCode(),
        this.invitationService.getInviteShareCard(),
        this.invitationService.getInvitePolicy(),
        this.invitationService.getInviteStats(),
      ]);
      if (
        codeResponse === null ||
        shareCardResponse === null ||
        policyResponse === null ||
        statsResponse === null
      ) {
        return;
      }
      const inviteeRewardContactDelta = policyResponse.invitee_reward_contact_delta;
      const inviterRewardContactDelta = policyResponse.inviter_reward_contact_delta;
      this.setData({
        myCode: codeResponse.code,
        shareText: '',
        shareTitle: shareCardResponse.title,
        sharePath: shareCardResponse.path,
        shareImageUrl: shareCardResponse.image_url,
        successInviteCount: statsResponse.inviter_success_bind_count,
        maxInviteCount: policyResponse.inviter_max_rewards_per_actor,
        inviterRewardContactDelta,
        inviteeRewardContactDelta,
        activityRewardHintText: buildRewardHintText(
          inviteeRewardContactDelta,
          inviterRewardContactDelta
        ),
        stepRewardHintText: buildRuleHintText(inviteeRewardContactDelta, inviterRewardContactDelta),
        ruleRewardHintText: buildRuleHintText(inviteeRewardContactDelta, inviterRewardContactDelta),
        rewardedContactLimitTotal: statsResponse.inviter_reward_contact_limit_actual_total,
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
      const shareCommandResponse = await this.invitationService.getInviteShareCommand();
      if (shareCommandResponse === null) {
        return;
      }
      const shareText = shareCommandResponse.text;
      if (shareText.trim() === '') {
        void wx.showToast({ title: '口令为空，请稍后重试', icon: 'none' });
        return;
      }

      this.setData({
        myCode: shareCommandResponse.code,
        shareText,
      });

      await wx.setClipboardData({ data: shareText });
      void this.invitationService
        .trackInviteEvent('copy_command', {
          code: shareCommandResponse.code,
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
    void this.invitationService
      .trackInviteEvent('share_wechat', {
        code: this.data.myCode,
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
