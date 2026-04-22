import { createPageLayoutData, type PageLayoutData } from '../../templates/page-layout';
import { createInviteBindService } from '../../services/pages/invite-bind-service';
import { classifyError } from '../../utils/error-classifier';
import { showAuthExpiredModalAndRelogin } from '../../utils/auth-expired-modal';
import { requireAuth } from '../../utils/auth-guard';
import { getLogger } from '../../utils/logger';
import inviteBindingService from '../../utils/invite-binding-service';

const logger = getLogger('InviteBind');

type InputEvent = WechatMiniprogram.CustomEvent<{ value: string }>;
type AuthGuardPage = WechatMiniprogram.Page.Instance<
  Record<string, unknown>,
  Record<string, unknown>
>;

interface InviteBindPageData extends Record<string, unknown> {
  pageLayoutData: PageLayoutData;
  bindCodeInput: string;
  submitting: boolean;
}

interface InviteBindPageCustom {
  invitationService: ReturnType<typeof createInviteBindService>;
  onInviteCodeInput(event: InputEvent): void;
  handleBindCode(): Promise<void>;
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

Page<InviteBindPageData, InviteBindPageCustom>({
  data: {
    pageLayoutData: createPageLayoutData({
      screenModel: {
        screenState: 'ready',
        contentVariant: 'data',
        refreshState: 'idle',
      },
      hasFooter: false,
    }),
    bindCodeInput: '',
    submitting: false,
  },

  invitationService: null as unknown as ReturnType<typeof createInviteBindService>,

  async onLoad() {
    this.invitationService = createInviteBindService();
    const isAuth = await requireAuth(this as unknown as AuthGuardPage);
    if (!isAuth) {
      return;
    }
    this.setData(buildScreenModelPayload('ready', 'data', 'idle'));
  },

  onUnload() {
    this.invitationService.dispose();
  },

  onInviteCodeInput(event) {
    this.setData({ bindCodeInput: event.detail.value });
  },

  async handleBindCode() {
    if (this.data.submitting) {
      return;
    }
    const code = this.data.bindCodeInput.trim().toUpperCase();
    if (code === '') {
      void wx.showToast({ title: '请输入邀请码', icon: 'none' });
      return;
    }

    try {
      this.setData({ submitting: true });
      const intake = await this.invitationService.intakeInviteCode(code);
      if (intake === null) {
        return;
      }
      if (!intake.valid || !intake.bindable || intake.recognized_code === null) {
        void wx.showToast({ title: '邀请码无效或不可绑定', icon: 'none' });
        return;
      }

      const bound = await this.invitationService.bindInviteCode(intake.recognized_code);
      if (bound === null) {
        return;
      }
      inviteBindingService.markBound();
      inviteBindingService.markDirty();
      this.setData({ bindCodeInput: '' });
      void wx.showToast({ title: '绑定成功', icon: 'success' });
    } catch (error) {
      const semantics = classifyError(error);
      if (semantics.reason === 'auth-invalid') {
        await showAuthExpiredModalAndRelogin();
        return;
      }
      if (error instanceof Error && error.message.includes('已绑定邀请码')) {
        inviteBindingService.markBound();
        inviteBindingService.markDirty();
      }
      logger.info('Bind invite code failed in invite bind page', { error });
      void wx.showToast({
        title:
          error instanceof Error && error.message !== '' ? error.message : '绑定失败，请稍后重试',
        icon: 'none',
      });
    } finally {
      this.setData({ submitting: false });
    }
  },
});
