import { requireAuth } from '../../utils/auth-guard';
import { getLogger } from '../../utils/logger';
import { promptContactRequestMessage, sendContactRequest } from '../../utils/contact-request';
import squareDiscoveryService, { type SquareContactViewModel } from '../../utils/discovery-service';
import { createPageLayoutData, type PageLayoutData } from '../../templates/page-layout';
import { isNonEmptyString } from '../../utils/guards';
import {
  SQUARE_CATEGORY,
  SQUARE_CATEGORY_ITEMS,
  type SquareCategory,
  type SquareCategoryItem,
} from '../../utils/constants/square';
import { type ScreenModel } from '../../services/pages/page-state';
import { createSquarePageService } from '../../services/pages/square-service';
import { showAuthExpiredModalAndRelogin } from '../../utils/auth-expired-modal';

const logger = getLogger('Square');

type AuthGuardPage = WechatMiniprogram.Page.Instance<
  Record<string, unknown>,
  Record<string, unknown>
>;

interface SquarePageData {
  pageLayoutData: PageLayoutData;
  categories: readonly SquareCategoryItem[];
  currentCategory: SquareCategory;
  contacts: SquareContactViewModel[];
  loading: boolean;
  nextRefreshAvailableAt: number | null;
}

interface LoadContactsOptions {
  respectCooldown?: boolean;
  silentOnCooldown?: boolean;
  showGlobalLoading?: boolean;
}

interface StrangerEntryPayload {
  qiaoId: string;
  nickname?: string;
  avatarUrl?: string;
  gender?: number | null;
  category?: string | number | null;
  bio?: string;
  region?: string;
}

interface SquarePageCustom {
  squarePageService: ReturnType<typeof createSquarePageService>;
  _blankFailureToastShown: boolean;
  applyScreenModel(screenModel: ScreenModel): void;
  notifyBlankLoadFailed(message: string): void;
  displayCachedContacts(): boolean;
  loadContactsWithCache(): void;
  revalidateCache(): Promise<void>;
  loadContacts(options?: LoadContactsOptions): Promise<void>;
  canRefreshNow(): boolean;
  getRefreshWaitSeconds(): number;
  selectCategory(event: WechatMiniprogram.TouchEvent): void;
  onPullDownRefresh(): void;
  handleContactTap(event: WechatMiniprogram.BaseEvent): void;
  handleAddContact(event: WechatMiniprogram.BaseEvent): Promise<void>;
  onUnload(): void;
}

const normalizeError = (error: unknown): Error => {
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

const showToast = (
  title: string,
  icon: WechatMiniprogram.ShowToastOption['icon'] = 'none'
): void => {
  void wx.showToast({ title, icon });
};

const getDatasetValue = (event: WechatMiniprogram.BaseEvent, key: string): unknown => {
  const dataset = event.currentTarget.dataset as Record<string, unknown> | undefined;
  return dataset?.[key];
};

const SQUARE_CATEGORY_VALUES = new Set<number>(Object.values(SQUARE_CATEGORY));

const isSquareCategory = (value: number): value is SquareCategory =>
  SQUARE_CATEGORY_VALUES.has(value);

const toSquareCategory = (value: unknown): SquareCategory | null => {
  if (value === null || value === undefined) {
    return null;
  }
  if (typeof value === 'number' && Number.isFinite(value)) {
    return isSquareCategory(value) ? value : null;
  }
  if (typeof value === 'string') {
    if (value === 'null' || value === '') {
      return null;
    }
    const parsed = Number.parseInt(value, 10);
    if (Number.isNaN(parsed)) {
      return null;
    }
    return isSquareCategory(parsed) ? parsed : null;
  }
  return null;
};

const toStringValue = (value: unknown): string | undefined => {
  if (typeof value === 'string') {
    return value;
  }
  if (typeof value === 'number') {
    return String(value);
  }
  return undefined;
};

const toJsonString = (payload: StrangerEntryPayload): string | null => {
  try {
    return JSON.stringify(payload);
  } catch {
    return null;
  }
};

const buildPageLayoutScreenModelPayload = (screenModel: ScreenModel): Record<string, unknown> => ({
  'pageLayoutData.screenModel': screenModel,
});

Page<SquarePageData, SquarePageCustom>({
  data: {
    pageLayoutData: createPageLayoutData({
      screenModel: {
        screenState: 'ready',
        contentVariant: 'data',
        refreshState: 'idle',
      },
      emptyMessage: '暂无联系人',
    }),
    categories: SQUARE_CATEGORY_ITEMS,
    currentCategory: SQUARE_CATEGORY.FRIEND,
    contacts: [],
    loading: false,
    nextRefreshAvailableAt: null,
  },

  _blankFailureToastShown: false,
  squarePageService: null as unknown as ReturnType<typeof createSquarePageService>,

  applyScreenModel(screenModel: ScreenModel) {
    this.setData(buildPageLayoutScreenModelPayload(screenModel));
  },

  notifyBlankLoadFailed(message: string) {
    if (this._blankFailureToastShown) {
      return;
    }
    this._blankFailureToastShown = true;
    showToast(message);
  },

  onLoad(options?: Record<string, string | undefined>) {
    this.squarePageService = createSquarePageService();
    const category = toSquareCategory(options?.category) ?? SQUARE_CATEGORY.FRIEND;
    this._blankFailureToastShown = false;
    this.setData({ currentCategory: category });
  },

  async onShow() {
    const isAuth = await requireAuth(this as unknown as AuthGuardPage);
    if (!isAuth) {
      return;
    }
    void this.loadContacts({
      respectCooldown: false,
      silentOnCooldown: true,
      showGlobalLoading: this.data.contacts.length === 0,
    });
  },
  displayCachedContacts() {
    const cacheResult = this.squarePageService.resolveCache(this.data.currentCategory);
    if (cacheResult === null) {
      return false;
    }
    this.setData({
      contacts: cacheResult.contacts,
      nextRefreshAvailableAt: cacheResult.nextRefreshAvailableAt,
      ...buildPageLayoutScreenModelPayload(cacheResult.screenModel),
    });
    if (cacheResult.shouldRevalidate) {
      void this.revalidateCache();
    }
    return true;
  },

  loadContactsWithCache() {
    if (this.displayCachedContacts()) {
      return;
    }
    void this.loadContacts({ respectCooldown: false });
  },

  async revalidateCache() {
    try {
      await this.loadContacts({
        respectCooldown: false,
        silentOnCooldown: true,
        showGlobalLoading: false,
      });
    } catch (error) {
      const err = normalizeError(error);
      logger.warn('Revalidation failed, keeping stale cache', { error: err.message });
    }
  },

  async loadContacts(options: LoadContactsOptions = {}) {
    const { respectCooldown = true, silentOnCooldown = false, showGlobalLoading = true } = options;
    if (respectCooldown && !this.canRefreshNow()) {
      if (!silentOnCooldown) {
        const waitSeconds = this.getRefreshWaitSeconds();
        showToast(waitSeconds > 0 ? '请' + waitSeconds + '秒后再试' : '还不能刷新');
      }
      return;
    }

    if (this.data.loading) {
      return;
    }

    this.setData({
      loading: true,
      ...(showGlobalLoading
        ? {
            ...buildPageLayoutScreenModelPayload({
              ...this.data.pageLayoutData.screenModel,
              screenState: 'ready',
              contentVariant: 'data',
              refreshState: 'refreshing',
            }),
          }
        : null),
    });

    const result = await this.squarePageService.load(this.data.currentCategory, {
      hasCurrentContent: this.data.contacts.length > 0,
      currentContacts: this.data.contacts,
    });
    if (result === null) {
      this.setData({ loading: false });
      return;
    }
    if (result.authInvalid) {
      this.setData({ loading: false });
      await showAuthExpiredModalAndRelogin();
      return;
    }

    if (result.shouldToastBlankFailure) {
      const errorMessage = isNonEmptyString(result.errorMessage) ? result.errorMessage : '加载失败';
      this.notifyBlankLoadFailed(errorMessage);
    } else if (result.screenModel.contentVariant !== 'blank') {
      this._blankFailureToastShown = false;
    }

    this.setData({
      loading: false,
      ...(result.screenModel.contentVariant === 'blank' ? null : { contacts: result.contacts }),
      nextRefreshAvailableAt: result.nextRefreshAvailableAt,
      ...buildPageLayoutScreenModelPayload(result.screenModel),
    });
  },

  canRefreshNow() {
    const { nextRefreshAvailableAt } = this.data;
    if (nextRefreshAvailableAt === null) {
      return true;
    }
    return Date.now() >= nextRefreshAvailableAt;
  },

  getRefreshWaitSeconds() {
    const { nextRefreshAvailableAt } = this.data;
    if (nextRefreshAvailableAt === null) {
      return 0;
    }
    const diffMs = nextRefreshAvailableAt - Date.now();
    const seconds = Math.ceil(diffMs / 1000);
    return seconds > 0 ? seconds : 0;
  },

  selectCategory(event) {
    const category = toSquareCategory(getDatasetValue(event, 'category'));
    if (category === null || category === this.data.currentCategory) {
      return;
    }

    this.setData({
      currentCategory: category,
      contacts: [],
      nextRefreshAvailableAt: null,
      ...buildPageLayoutScreenModelPayload({
        screenState: 'ready',
        contentVariant: 'data',
        refreshState: 'idle',
      }),
    });

    this.loadContactsWithCache();
  },

  onPullDownRefresh() {
    void this.loadContacts().finally(() => {
      void wx.stopPullDownRefresh();
    });
  },

  onUnload() {
    this.squarePageService.dispose();
  },

  handleContactTap(event) {
    const qiaoId = toStringValue(getDatasetValue(event, 'id'));
    if (!isNonEmptyString(qiaoId)) {
      return;
    }
    const contact = this.data.contacts.find((item) => item.qiao_id === qiaoId) ?? null;

    void wx.navigateTo({
      url: `/pages/stranger-info/stranger-info?id=${qiaoId}`,
      success: (res) => {
        if (contact === null) {
          return;
        }
        const payload: StrangerEntryPayload = {
          qiaoId: contact.qiao_id,
          nickname: contact.nickname,
          avatarUrl: contact.avatar_url,
          gender: contact.gender,
          category: contact.category,
          bio: contact.bio,
          region: contact.region,
        };
        const payloadString = toJsonString(payload);
        if (isNonEmptyString(payloadString)) {
          res.eventChannel.emit('stranger-entry', payloadString);
          return;
        }
        res.eventChannel.emit('stranger-entry', JSON.stringify({ qiaoId: contact.qiao_id }));
      },
    });
  },

  async handleAddContact(event) {
    const qiaoId = toStringValue(getDatasetValue(event, 'id'));
    if (!isNonEmptyString(qiaoId)) {
      return;
    }

    const originalContacts = [...this.data.contacts];
    const message = await promptContactRequestMessage();
    if (message === null) {
      return;
    }

    void wx.showLoading({ title: '发送中...', mask: true });

    try {
      await sendContactRequest({ qiaoId, message });

      void wx.hideLoading();
      showToast('请求已发送', 'success');

      const updatedContacts = originalContacts.filter((contact) => contact.qiao_id !== qiaoId);
      this.setData({
        contacts: updatedContacts,
        ...buildPageLayoutScreenModelPayload({
          screenState: 'ready',
          contentVariant: updatedContacts.length === 0 ? 'empty' : 'data',
          refreshState: this.data.pageLayoutData.screenModel.refreshState,
        }),
      });

      squareDiscoveryService.clearCache(this.data.currentCategory);

      void this.loadContacts({ silentOnCooldown: true, showGlobalLoading: false }).catch(
        (error) => {
          const err = normalizeError(error);
          logger.warn('Square page refresh failed after add contact', { error: err.message });
        }
      );

      logger.info('Contact request sent', { to_qiao_id: qiaoId });
    } catch (error) {
      const err = normalizeError(error);
      void wx.hideLoading();
      const failureMessage = isNonEmptyString(err.message) ? err.message : '发送失败';
      showToast(failureMessage);
      logger.error('Failed to send contact request', {
        to_qiao_id: qiaoId,
        error: failureMessage,
      });
      this.setData({ contacts: originalContacts });
    }
  },
});
