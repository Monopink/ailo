import {
  createStrangerInfoPageService,
  type StrangerEntryPayload,
  type StrangerInfoPageService,
  type StrangerProfileView,
} from '../services/pages/stranger-info-service';
import { createPageLayoutData, type PageLayoutData } from '../../templates/page-layout';
import {
  isContactRequestLimitExceededError,
  promptContactRequestMessage,
  sendContactRequest,
} from '../utils/contact-request';
import { normalizeError } from '../../utils/errors';
import { classifyError } from '../../utils/error-classifier';
import { isNonEmptyString } from '../../utils/guards';
import { getLogger } from '../../utils/logger';
import { showAuthExpiredModalAndRelogin } from '../../utils/auth-expired-modal';
import { type ScreenModel } from '../services/pages/page-state';
import authService from '../../utils/auth-service';
import { canUseInviteCapability } from '../../utils/access-capability';

const logger = getLogger('StrangerInfo');

interface StrangerInfoPageData {
  qiaoId: string;
  profile: StrangerProfileView | null;
  pageLayoutData: PageLayoutData;
}

interface StrangerInfoPageCustom {
  strangerInfoService: StrangerInfoPageService;
  _hasEntryRenderData: boolean;
  normalizeEntryPayload(raw: unknown, expectedQiaoId: string): StrangerEntryPayload | null;
  consumeEntryPayload(expectedQiaoId: string): Promise<StrangerEntryPayload | null>;
  applyScreenModel(screenModel: ScreenModel): void;
  loadProfile(): Promise<void>;
  handleAddContact(): Promise<void>;
  promptContactLimitReached(): Promise<void>;
  sendContactRequest(message: string): Promise<void>;
}

interface StrangerInfoLoadOptions extends Record<string, string | undefined> {
  id?: string;
}

const buildPageLayoutScreenModelPayload = (screenModel: ScreenModel): Record<string, unknown> => ({
  'pageLayoutData.screenModel': screenModel,
});

const toEntryRecord = (raw: unknown): Record<string, unknown> | null => {
  if (typeof raw === 'string') {
    try {
      const parsed = JSON.parse(raw) as unknown;
      if (parsed !== null && typeof parsed === 'object') {
        return parsed as Record<string, unknown>;
      }
      return null;
    } catch {
      return null;
    }
  }
  if (raw === null || typeof raw !== 'object') {
    return null;
  }
  return raw as Record<string, unknown>;
};

const resolveEntryQiaoId = (record: Record<string, unknown>): string => {
  if (typeof record.qiaoId === 'string') {
    return record.qiaoId;
  }
  if (typeof record.qiao_id === 'string') {
    return record.qiao_id;
  }
  return '';
};

const pickString = (record: Record<string, unknown>, key: string): string | undefined => {
  const value = record[key];
  return typeof value === 'string' ? value : undefined;
};

const pickCategory = (record: Record<string, unknown>): string | null | undefined => {
  if (typeof record.categoryKey === 'string') {
    return record.categoryKey;
  }
  if (typeof record.category_key === 'string') {
    return record.category_key;
  }
  if (record.categoryKey === null || record.category_key === null) {
    return null;
  }
  return undefined;
};

const hasRenderableEntryPayload = (payload: StrangerEntryPayload | null): boolean => {
  if (payload === null) {
    return false;
  }

  const textFields: Array<string | null | undefined> = [
    payload.nickname,
    payload.avatarUrl,
    typeof payload.remark === 'string' ? payload.remark : undefined,
    payload.bio,
    payload.region,
    payload.categoryKey,
    payload.categoryTitle,
  ];

  if (textFields.some((value) => isNonEmptyString(value))) {
    return true;
  }

  if (Array.isArray(payload.tags) && payload.tags.length > 0) {
    return true;
  }

  return typeof payload.gender === 'number' && payload.gender > 0;
};

Page<StrangerInfoPageData, StrangerInfoPageCustom>({
  data: {
    qiaoId: '',
    profile: null,
    pageLayoutData: createPageLayoutData({
      screenModel: {
        screenState: 'booting',
        contentVariant: 'blank',
        refreshState: 'idle',
      },
      hasFooter: false,
    }),
  },

  strangerInfoService: null as unknown as StrangerInfoPageService,
  _hasEntryRenderData: false,

  normalizeEntryPayload(raw: unknown, expectedQiaoId: string): StrangerEntryPayload | null {
    const record = toEntryRecord(raw);
    if (record === null) {
      return null;
    }
    const qiaoIdCandidate = resolveEntryQiaoId(record);
    if (!isNonEmptyString(qiaoIdCandidate) || qiaoIdCandidate !== expectedQiaoId) {
      return null;
    }

    const payload: StrangerEntryPayload = {
      qiaoId: qiaoIdCandidate,
    };

    payload.nickname = pickString(record, 'nickname');
    payload.username = pickString(record, 'username');
    payload.avatarUrl = pickString(record, 'avatarUrl') ?? pickString(record, 'avatar_url');
    if (typeof record.gender === 'number' || record.gender === null) {
      payload.gender = record.gender;
    }
    const categoryKey = pickCategory(record);
    payload.categoryKey = typeof categoryKey === 'string' ? categoryKey : null;
    payload.categoryTitle =
      pickString(record, 'categoryTitle') ?? pickString(record, 'category_title');
    if (Array.isArray(record.tags)) {
      payload.tags = record.tags.filter((tag): tag is string => typeof tag === 'string');
    }
    if (typeof record.remark === 'string' || record.remark === null) {
      payload.remark = record.remark;
    }
    payload.bio = pickString(record, 'bio');
    payload.region = pickString(record, 'region');
    return payload;
  },

  async consumeEntryPayload(expectedQiaoId: string): Promise<StrangerEntryPayload | null> {
    const pageInstance = this as unknown as {
      getOpenerEventChannel?: () => WechatMiniprogram.EventChannel;
    };
    const eventChannel =
      typeof pageInstance.getOpenerEventChannel === 'function'
        ? pageInstance.getOpenerEventChannel()
        : null;
    if (eventChannel === null) {
      return null;
    }

    return await new Promise((resolve) => {
      let resolved = false;
      const finalize = (payload: StrangerEntryPayload | null): void => {
        if (resolved) {
          return;
        }
        resolved = true;
        resolve(payload);
      };
      eventChannel.once('stranger-entry', (rawPayload) => {
        finalize(this.normalizeEntryPayload(rawPayload, expectedQiaoId));
      });
      setTimeout(() => {
        finalize(null);
      }, 120);
    });
  },

  applyScreenModel(screenModel: ScreenModel) {
    this.setData(buildPageLayoutScreenModelPayload(screenModel));
  },

  async onLoad(options: StrangerInfoLoadOptions) {
    // Recreate service per page lifecycle to avoid reusing a disposed instance.
    this.strangerInfoService = createStrangerInfoPageService();
    const qiaoId = options.id;

    if (!isNonEmptyString(qiaoId)) {
      this.applyScreenModel({
        screenState: 'ready',
        contentVariant: 'blank',
        refreshState: 'idle',
      });
      return;
    }

    const entryPayload = await this.consumeEntryPayload(qiaoId);
    this._hasEntryRenderData = hasRenderableEntryPayload(entryPayload);

    this.setData({
      qiaoId,
    });

    const bootstrapResult = await this.strangerInfoService.bootstrap(qiaoId, entryPayload);
    if (bootstrapResult === null) {
      return;
    }
    this.setData({
      profile: bootstrapResult.profile,
      ...buildPageLayoutScreenModelPayload(bootstrapResult.screenModel),
    });

    void this.loadProfile();
  },

  onUnload() {
    this.strangerInfoService.dispose();
  },

  async loadProfile() {
    const { qiaoId, profile } = this.data;
    if (!isNonEmptyString(qiaoId) || profile === null) {
      this.applyScreenModel({
        screenState: 'ready',
        contentVariant: 'data',
        refreshState: 'degraded',
      });
      return;
    }

    this.applyScreenModel({
      ...this.data.pageLayoutData.screenModel,
      screenState: 'ready',
      contentVariant: 'data',
      refreshState: 'refreshing',
    });

    const result = await this.strangerInfoService.refresh(qiaoId, profile, profile.categoryKey);
    if (result === null) {
      return;
    }

    this.applyScreenModel(result.screenModel);
    if (result.profile !== null) {
      this.setData({ profile: result.profile });
    }
    if (result.authInvalid) {
      await showAuthExpiredModalAndRelogin();
      return;
    }
    if (!this._hasEntryRenderData && result.profile === null) {
      this.applyScreenModel({
        screenState: 'ready',
        contentVariant: 'data',
        refreshState: 'degraded',
      });
    }

    logger.info('Stranger profile loaded', { qiao_id: qiaoId });
  },

  async handleAddContact() {
    const profile = this.data.profile;
    if (profile === null) {
      return;
    }

    try {
      const availableTotal = await this.strangerInfoService.getCurrentContactLimit();
      if (availableTotal <= 0) {
        await this.promptContactLimitReached();
        return;
      }
    } catch (error: unknown) {
      const err = normalizeError(error);
      logger.warn('Failed to fetch ai contact limit before add contact', { error: err.message });
    }

    const message = await promptContactRequestMessage();
    if (message === null) {
      return;
    }

    await this.sendContactRequest(message);
  },

  async promptContactLimitReached() {
    const canUseInvite = canUseInviteCapability(authService.getUserInfo());
    if (!canUseInvite) {
      await wx.showModal({
        title: '联系人达到上限',
        content: '联系人达到上限，先和他们聊聊吧。',
        showCancel: false,
        confirmText: '我知道了',
      });
      return;
    }

    const result = await new Promise<WechatMiniprogram.ShowModalSuccessCallbackResult>(
      (resolve) => {
        wx.showModal({
          title: '联系人达到上限',
          content: '联系人达到上限，先和他们聊聊吧。',
          cancelText: '好',
          confirmText: '增加上限',
          success: resolve,
          fail: () =>
            resolve({ confirm: false, cancel: true, content: '', errMsg: 'showModal:fail' }),
        });
      }
    );

    if (!result.confirm) {
      return;
    }
    void wx.navigateTo({ url: '/pages/invite-share/invite-share' });
  },

  async sendContactRequest(message: string) {
    try {
      void wx.showLoading({ title: '发送中...' });

      await sendContactRequest({
        qiaoId: this.data.qiaoId,
        message,
        categoryKey: this.data.profile?.categoryKey,
      });

      void wx.hideLoading();
      void wx.showToast({
        title: '已发送',
        icon: 'success',
      });

      logger.info('Contact request sent', { qiao_id: this.data.qiaoId });

      const pageInstance = this as unknown as {
        getOpenerEventChannel?: () => WechatMiniprogram.EventChannel;
      };
      const eventChannel =
        typeof pageInstance.getOpenerEventChannel === 'function'
          ? pageInstance.getOpenerEventChannel()
          : null;
      if (eventChannel !== null) {
        eventChannel.emit('contact-request-sent', { qiaoId: this.data.qiaoId });
      }

      setTimeout(() => {
        void wx.navigateBack();
      }, 1500);
    } catch (error: unknown) {
      void wx.hideLoading();
      const semantics = classifyError(error);
      if (semantics.reason === 'auth-invalid') {
        await showAuthExpiredModalAndRelogin();
        return;
      }

      if (isContactRequestLimitExceededError(error)) {
        await this.promptContactLimitReached();
        return;
      }

      const err = normalizeError(error);
      logger.error('Failed to send contact request', { error: err.message });

      void wx.showToast({
        title: isNonEmptyString(err.message) ? err.message : '发送失败',
        icon: 'none',
      });
    }
  },
});
