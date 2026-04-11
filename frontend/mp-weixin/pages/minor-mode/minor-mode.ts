import { requireAuth } from '../../utils/auth-guard';
import { getLogger } from '../../utils/logger';
import { showAuthExpiredModalAndRelogin } from '../../utils/auth-expired-modal';
import {
  isMinorModeDiscoveryBlockedNow,
  MINOR_MODE_DISCOVERY_BLOCK_END_HOUR,
  MINOR_MODE_DISCOVERY_BLOCK_START_HOUR,
  type MinorModeStatus,
} from '../../utils/minor-mode';
import { createMinorModePageService } from '../../services/pages/minor-mode-service';

const logger = getLogger('MinorModePage');

type AuthGuardPage = WechatMiniprogram.Page.Instance<
  Record<string, unknown>,
  Record<string, unknown>
>;

type MinorModeStep =
  | 'intro'
  | 'enable-set-pin'
  | 'enable-confirm-pin'
  | 'disable-verify-pin'
  | 'change-verify-old-pin'
  | 'change-set-new-pin'
  | 'change-confirm-new-pin';

const MAX_LOCAL_PIN_FAILURES = 5;
const LOCAL_PIN_LOCK_MS = 15 * 60 * 1000;
const PIN_INVALID_REASON = 'MINOR_MODE_PIN_INVALID';
const STATUS_CHANGE_EVENT = 'statusChanged';
const NAVIGATE_BACK_DELAY_MS = 250;

interface MinorModePageData extends Record<string, unknown> {
  loading: boolean;
  submitting: boolean;
  status: MinorModeStatus | null;
  step: MinorModeStep;
  pinInput: string;
  pinFocused: boolean;
  pinCells: number[];
  primaryPin: string;
  verifiedOldPin: string;
  pinFailCount: number;
  pinLockUntilMs: number | null;
}

interface MinorModePageCustom {
  minorModePageService: ReturnType<typeof createMinorModePageService>;
  loadMinorModeStatus(): Promise<void>;
  onPinInput(event: WechatMiniprogram.CustomEvent<{ value?: string }>): void;
  focusPinInput(): void;
  onPinBlur(): void;
  handlePrimaryAction(): void;
  startChangePinFlow(): void;
  submitStep(): Promise<void>;
  submitEnable(): Promise<void>;
  submitDisable(): Promise<void>;
  verifyOldPinForUpdate(): Promise<void>;
  submitPinUpdate(): Promise<void>;
  returnToIntro(): void;
  clearFlowFields(): void;
  isPinLocallyLocked(): boolean;
  handlePinInvalidFailure(): void;
  resetPinFailureState(): void;
  getPinLockRemainingMinutes(): number;
  notifyStatusChanged(): void;
  navigateBackAfterMutation(): void;
}

const normalizePinInput = (value: unknown): string => {
  if (typeof value !== 'string') {
    return '';
  }
  const onlyDigits = value.replace(/\D/g, '');
  return onlyDigits.slice(0, 4);
};

const isValidPin = (value: string): boolean => /^\d{4}$/.test(value);

const showToast = (title: string): void => {
  void wx.showToast({
    title,
    icon: 'none',
  });
};

Page<MinorModePageData, MinorModePageCustom>({
  data: {
    loading: false,
    submitting: false,
    status: null,
    step: 'intro',
    pinInput: '',
    pinFocused: false,
    pinCells: [0, 1, 2, 3],
    primaryPin: '',
    verifiedOldPin: '',
    pinFailCount: 0,
    pinLockUntilMs: null,
  },

  minorModePageService: null as unknown as ReturnType<typeof createMinorModePageService>,

  async onLoad() {
    this.minorModePageService = createMinorModePageService();
    const isAuth = await requireAuth(this as unknown as AuthGuardPage);
    if (!isAuth) {
      return;
    }
    await this.loadMinorModeStatus();
  },

  onUnload() {
    this.minorModePageService.dispose();
  },

  async loadMinorModeStatus() {
    this.setData({ loading: true });
    const result = await this.minorModePageService.load();
    if (result === null) {
      this.setData({ loading: false });
      return;
    }
    if (result.authInvalid) {
      this.setData({ loading: false });
      await showAuthExpiredModalAndRelogin();
      return;
    }
    this.setData({
      loading: false,
      status: result.status,
      step: 'intro',
      pinInput: '',
      pinFocused: false,
      primaryPin: '',
      verifiedOldPin: '',
    });
  },

  onPinInput(event) {
    this.setData({
      pinInput: normalizePinInput(event.detail.value),
      pinFocused: true,
    });
  },

  focusPinInput() {
    this.setData({ pinFocused: true });
  },

  onPinBlur() {
    this.setData({ pinFocused: false });
  },

  clearFlowFields() {
    this.setData({
      pinInput: '',
      pinFocused: false,
      primaryPin: '',
      verifiedOldPin: '',
    });
  },

  returnToIntro() {
    this.setData({ step: 'intro' });
    this.clearFlowFields();
  },

  handlePrimaryAction() {
    const enabled = this.data.status?.enabled === true;
    this.clearFlowFields();
    this.setData({
      step: enabled ? 'disable-verify-pin' : 'enable-set-pin',
      pinFocused: true,
    });
  },

  startChangePinFlow() {
    if (this.data.status?.enabled !== true) {
      return;
    }
    this.clearFlowFields();
    this.setData({
      step: 'change-verify-old-pin',
      pinFocused: true,
    });
  },

  isPinLocallyLocked() {
    const { pinLockUntilMs } = this.data;
    if (typeof pinLockUntilMs !== 'number') {
      return false;
    }
    return Date.now() < pinLockUntilMs;
  },

  getPinLockRemainingMinutes() {
    const { pinLockUntilMs } = this.data;
    if (typeof pinLockUntilMs !== 'number') {
      return 0;
    }
    const remainingMs = pinLockUntilMs - Date.now();
    if (remainingMs <= 0) {
      return 0;
    }
    return Math.ceil(remainingMs / 60000);
  },

  handlePinInvalidFailure() {
    const failCount = this.data.pinFailCount + 1;
    if (failCount >= MAX_LOCAL_PIN_FAILURES) {
      this.setData({
        pinFailCount: failCount,
        pinLockUntilMs: Date.now() + LOCAL_PIN_LOCK_MS,
      });
      showToast('尝试次数过多，请稍后再试');
      return;
    }
    this.setData({ pinFailCount: failCount });
  },

  resetPinFailureState() {
    this.setData({
      pinFailCount: 0,
      pinLockUntilMs: null,
    });
  },

  notifyStatusChanged() {
    try {
      const eventChannel = this.getOpenerEventChannel();
      eventChannel.emit(STATUS_CHANGE_EVENT);
    } catch (error: unknown) {
      logger.warn('No opener event channel for status change', { error });
    }
  },

  navigateBackAfterMutation() {
    setTimeout(() => {
      void wx.navigateBack();
    }, NAVIGATE_BACK_DELAY_MS);
  },

  async submitEnable() {
    if (this.data.submitting) {
      return;
    }
    if (!isValidPin(this.data.primaryPin)) {
      showToast('请输入4位数字密码');
      return;
    }

    this.setData({ submitting: true });
    const result = await this.minorModePageService.enable(this.data.primaryPin);
    this.setData({ submitting: false });
    if (result.authInvalid) {
      await showAuthExpiredModalAndRelogin();
      return;
    }
    if (result.status === null) {
      showToast('开启失败，请稍后重试');
      return;
    }

    this.setData({
      status: result.status,
      step: 'intro',
    });
    this.clearFlowFields();
    this.resetPinFailureState();
    showToast('青少年模式已开启');
    this.notifyStatusChanged();
    this.navigateBackAfterMutation();
  },

  async submitDisable() {
    if (this.data.submitting) {
      return;
    }
    if (this.isPinLocallyLocked()) {
      const remainingMinutes = this.getPinLockRemainingMinutes();
      showToast(`输入错误次数过多，请${remainingMinutes}分钟后重试`);
      return;
    }
    if (!isValidPin(this.data.pinInput)) {
      showToast('请输入4位数字密码');
      return;
    }

    this.setData({ submitting: true });
    const result = await this.minorModePageService.disable(this.data.pinInput);
    this.setData({ submitting: false });
    if (result.authInvalid) {
      await showAuthExpiredModalAndRelogin();
      return;
    }
    if (result.status === null) {
      if (result.reason === PIN_INVALID_REASON) {
        this.handlePinInvalidFailure();
        showToast('密码错误，请重试');
        return;
      }
      showToast('关闭失败，请稍后重试');
      return;
    }

    this.setData({
      status: result.status,
      step: 'intro',
    });
    this.clearFlowFields();
    this.resetPinFailureState();
    showToast('青少年模式已关闭');
    this.notifyStatusChanged();
    this.navigateBackAfterMutation();
  },

  async verifyOldPinForUpdate() {
    if (this.data.submitting) {
      return;
    }
    if (this.isPinLocallyLocked()) {
      const remainingMinutes = this.getPinLockRemainingMinutes();
      showToast(`输入错误次数过多，请${remainingMinutes}分钟后重试`);
      return;
    }
    if (!isValidPin(this.data.pinInput)) {
      showToast('请输入当前4位密码');
      return;
    }

    this.setData({ submitting: true });
    const result = await this.minorModePageService.verifyPin(this.data.pinInput);
    this.setData({ submitting: false });
    if (result.authInvalid) {
      await showAuthExpiredModalAndRelogin();
      return;
    }
    if (result.verified !== true) {
      if (result.reason === PIN_INVALID_REASON || result.verified === false) {
        this.handlePinInvalidFailure();
        showToast('当前密码错误，请重试');
        return;
      }
      showToast('校验失败，请稍后重试');
      return;
    }

    this.setData({
      verifiedOldPin: this.data.pinInput,
      pinInput: '',
      step: 'change-set-new-pin',
      pinFocused: true,
    });
    this.resetPinFailureState();
  },

  async submitPinUpdate() {
    if (this.data.submitting) {
      return;
    }
    if (this.isPinLocallyLocked()) {
      const remainingMinutes = this.getPinLockRemainingMinutes();
      showToast(`输入错误次数过多，请${remainingMinutes}分钟后重试`);
      return;
    }
    if (!isValidPin(this.data.verifiedOldPin)) {
      showToast('请先校验当前密码');
      this.setData({ step: 'change-verify-old-pin' });
      return;
    }
    if (!isValidPin(this.data.primaryPin)) {
      showToast('请输入新的4位数字密码');
      this.setData({ step: 'change-set-new-pin' });
      return;
    }
    if (this.data.pinInput !== this.data.primaryPin) {
      showToast('两次输入新密码不一致');
      return;
    }

    this.setData({ submitting: true });
    const result = await this.minorModePageService.updatePin(
      this.data.verifiedOldPin,
      this.data.primaryPin
    );
    this.setData({ submitting: false });
    if (result.authInvalid) {
      await showAuthExpiredModalAndRelogin();
      return;
    }
    if (result.status === null) {
      if (result.reason === PIN_INVALID_REASON) {
        this.handlePinInvalidFailure();
        showToast('当前密码错误，请重试');
        this.setData({ step: 'change-verify-old-pin' });
        return;
      }
      showToast('修改失败，请稍后重试');
      return;
    }

    this.setData({
      status: result.status,
      step: 'intro',
    });
    this.clearFlowFields();
    this.resetPinFailureState();
    showToast('密码修改成功');
  },

  async submitStep() {
    switch (this.data.step) {
      case 'enable-set-pin':
        if (!isValidPin(this.data.pinInput)) {
          showToast('请输入4位数字密码');
          return;
        }
        this.setData({
          primaryPin: this.data.pinInput,
          pinInput: '',
          step: 'enable-confirm-pin',
          pinFocused: true,
        });
        return;

      case 'enable-confirm-pin':
        if (!isValidPin(this.data.pinInput)) {
          showToast('请输入4位数字密码');
          return;
        }
        if (this.data.pinInput !== this.data.primaryPin) {
          showToast('两次输入密码不一致');
          return;
        }
        await this.submitEnable();
        return;

      case 'disable-verify-pin':
        await this.submitDisable();
        return;

      case 'change-verify-old-pin':
        await this.verifyOldPinForUpdate();
        return;

      case 'change-set-new-pin':
        if (!isValidPin(this.data.pinInput)) {
          showToast('请输入新的4位数字密码');
          return;
        }
        this.setData({
          primaryPin: this.data.pinInput,
          pinInput: '',
          step: 'change-confirm-new-pin',
          pinFocused: true,
        });
        return;

      case 'change-confirm-new-pin':
        if (!isValidPin(this.data.pinInput)) {
          showToast('请输入新的4位数字密码');
          return;
        }
        await this.submitPinUpdate();
        return;

      default:
        return;
    }
  },

  onShow() {
    const blockedNow = isMinorModeDiscoveryBlockedNow();
    logger.info('Minor mode page shown', {
      blockedNow,
      blockWindow: `${MINOR_MODE_DISCOVERY_BLOCK_START_HOUR}:00-${MINOR_MODE_DISCOVERY_BLOCK_END_HOUR}:00`,
    });
  },

  onHide() {
    const lockUntil = this.data.pinLockUntilMs;
    if (typeof lockUntil === 'number' && lockUntil <= Date.now()) {
      this.resetPinFailureState();
    }
  },
});
