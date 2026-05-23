import { requireAuth } from '../../utils/auth-guard';
import { showAuthExpiredModalAndRelogin } from '../../utils/auth-expired-modal';
import { promptContactRequestMessage, sendContactRequest } from '../utils/contact-request';
import {
  SQUARE_CATEGORIES_CACHE_STALE_PERIOD_MS,
  SQUARE_CATEGORIES_CACHE_TTL_MS,
} from '../../utils/discovery-service';
import squareDiscoveryService, { type SquareContactViewModel } from '../../utils/discovery-service';
import { isValidCategoryKey, type SquareCategoryCard } from '../../utils/constants/square';
import { createPageLayoutData, type PageLayoutData } from '../../templates/page-layout';
import { isNonEmptyString } from '../../utils/guards';
import { getLogger } from '../../utils/logger';
import {
  fetchMinorModeStatus,
  getCachedMinorModeStatus,
  isMinorModeDiscoveryRestricted,
} from '../../utils/minor-mode';
import { type ScreenModel } from '../services/pages/page-state';
import {
  createSquarePageService,
  type SquareEndReason,
  type SquareLoadMode,
} from '../services/pages/square-service';

const logger = getLogger('Square');

type AuthGuardPage = WechatMiniprogram.Page.Instance<
  Record<string, unknown>,
  Record<string, unknown>
>;

interface SquarePageData {
  pageLayoutData: PageLayoutData;
  categories: SquareCategoryCard[];
  currentCategoryKey: string;
  contacts: SquareContactViewModel[];
  loading: boolean;
  loadingMore: boolean;
  nextCursor: string | null;
  hasMore: boolean;
  currentPageIndex: number;
  maxPagesPerFeed: number;
  endReason: SquareEndReason;
  refreshRemainingSeconds: number;
  nextRefreshAvailableAt: number | null;
  refreshIntervalSeconds: number;
  refreshInfoText: string;
  blankMessage: string;
  minorModeDiscoveryBlocked: boolean;
}

interface LoadContactsOptions {
  mode?: SquareLoadMode;
  showGlobalLoading?: boolean;
}

interface StrangerEntryPayload {
  qiaoId: string;
  nickname?: string;
  avatarUrl?: string;
  gender?: number | null;
  categoryKey?: string | null;
  categoryTitle?: string;
  tags?: string[];
  remark?: string | null;
  bio?: string;
  region?: string;
}

interface ContactRequestSentPayload {
  qiaoId?: string;
}

interface SquarePageCustom {
  squarePageService: ReturnType<typeof createSquarePageService>;
  _blankFailureToastShown: boolean;
  _requestedCategoryKey: string | null;
  _initialized: boolean;
  _removedQiaoIds: Set<string>;
  _refreshCountdownTimer: number | null;
  ensureMinorModeAllowed(): Promise<boolean>;
  applyScreenModel(screenModel: ScreenModel): void;
  notifyBlankLoadFailed(message: string): void;
  switchToEntry(toastMessage?: string): Promise<void>;
  applyCategories(
    categories: SquareCategoryCard[],
    preferredKey?: string | null,
    strictPreferred?: boolean
  ): boolean;
  bootstrapCategories(): void;
  refreshCategories(): Promise<boolean>;
  filterRemovedContacts(contacts: SquareContactViewModel[]): SquareContactViewModel[];
  initializeOnce(): Promise<void>;
  applyLoadingState(mode: SquareLoadMode, showGlobalLoading: boolean): void;
  handleLoadResult(
    mode: SquareLoadMode,
    result: Awaited<ReturnType<ReturnType<typeof createSquarePageService>['load']>>
  ): Promise<boolean>;
  applyFinalLoadResult(
    result: NonNullable<Awaited<ReturnType<ReturnType<typeof createSquarePageService>['load']>>>
  ): void;
  loadContacts(options?: LoadContactsOptions): Promise<void>;
  selectCategory(event: WechatMiniprogram.TouchEvent): void;
  handleContentReachBottom(): void;
  handleContactTap(event: WechatMiniprogram.BaseEvent): void;
  handleStrangerContactRequestSent(payload: ContactRequestSentPayload): void;
  removeContactFromCurrentView(qiaoId: string): void;
  updateRefreshInfoBar(): void;
  startRefreshCountdown(): void;
  stopRefreshCountdown(): void;
  formatRefreshInfoText(): string;
  handleAddContact(event: WechatMiniprogram.BaseEvent): Promise<void>;
  onHide(): void;
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

const BLOCKED_SCREEN_MODEL: ScreenModel = {
  screenState: 'ready',
  contentVariant: 'blank',
  refreshState: 'idle',
};

const getDatasetValue = (event: WechatMiniprogram.BaseEvent, key: string): unknown => {
  const dataset = event.currentTarget.dataset as Record<string, unknown> | undefined;
  return dataset?.[key];
};

const toCategoryKey = (value: unknown): string | null => {
  if (typeof value === 'string' && isValidCategoryKey(value)) {
    return value;
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

const formatTimestamp = (timestampMs: number): string => {
  const date = new Date(timestampMs);
  const month = `${date.getMonth() + 1}`.padStart(2, '0');
  const day = `${date.getDate()}`.padStart(2, '0');
  const hours = `${date.getHours()}`.padStart(2, '0');
  const minutes = `${date.getMinutes()}`.padStart(2, '0');
  return `${month}-${day} ${hours}:${minutes}`;
};

const formatDuration = (seconds: number): string => {
  const normalized = Math.max(0, seconds);
  const hours = Math.floor(normalized / 3600);
  const minutes = Math.floor((normalized % 3600) / 60);
  const remainSeconds = normalized % 60;
  if (hours > 0) {
    return `${hours}小时${minutes}分${remainSeconds}秒`;
  }
  if (minutes > 0) {
    return `${minutes}分${remainSeconds}秒`;
  }
  return `${remainSeconds}秒`;
};

Page<SquarePageData, SquarePageCustom>({
  data: {
    pageLayoutData: createPageLayoutData({
      screenModel: {
        screenState: 'ready',
        contentVariant: 'data',
        refreshState: 'idle',
      },
      emptyMessage: '暂无内容',
    }),
    categories: squareDiscoveryService.getFallbackCategories(),
    currentCategoryKey: 'friend',
    contacts: [],
    loading: false,
    loadingMore: false,
    nextCursor: null,
    hasMore: true,
    currentPageIndex: 1,
    maxPagesPerFeed: 1,
    endReason: null,
    refreshRemainingSeconds: 0,
    nextRefreshAvailableAt: null,
    refreshIntervalSeconds: 0,
    refreshInfoText: '刷新信息加载中',
    blankMessage: '页面暂时不可用，请稍后重试',
    minorModeDiscoveryBlocked: false,
  },

  _blankFailureToastShown: false,
  _requestedCategoryKey: null,
  _initialized: false,
  _removedQiaoIds: new Set<string>(),
  _refreshCountdownTimer: null,
  squarePageService: null as unknown as ReturnType<typeof createSquarePageService>,

  applyScreenModel(screenModel) {
    this.setData(buildPageLayoutScreenModelPayload(screenModel));
  },

  notifyBlankLoadFailed(message: string) {
    if (this._blankFailureToastShown) {
      return;
    }
    this._blankFailureToastShown = true;
    showToast(message);
  },

  async switchToEntry(toastMessage?: string) {
    await new Promise<void>((resolve) => {
      void wx.switchTab({
        url: '/pages/square-entry/square-entry',
        success: () => {
          if (isNonEmptyString(toastMessage)) {
            showToast(toastMessage);
          }
          resolve();
        },
        fail: () => {
          if (isNonEmptyString(toastMessage)) {
            showToast(toastMessage);
          }
          resolve();
        },
      });
    });
  },

  applyCategories(categories, preferredKey = null, strictPreferred = false) {
    const normalized = categories.filter((item) => isValidCategoryKey(item.categoryKey));
    if (normalized.length === 0) {
      this.setData({
        categories: [],
        contacts: [],
        hasMore: false,
        nextCursor: null,
        currentPageIndex: 1,
        maxPagesPerFeed: 1,
        endReason: null,
        ...buildPageLayoutScreenModelPayload({
          screenState: 'ready',
          contentVariant: 'empty',
          refreshState: 'idle',
        }),
      });
      return false;
    }

    const availableKeys = new Set(normalized.map((item) => item.categoryKey));
    const currentKey = this.data.currentCategoryKey;
    let nextKey = currentKey;
    const preferred =
      typeof preferredKey === 'string' && preferredKey.length > 0 ? preferredKey : null;

    if (
      strictPreferred &&
      preferred !== null &&
      isValidCategoryKey(preferred) &&
      !availableKeys.has(preferred)
    ) {
      void this.switchToEntry('暂无内容');
      return false;
    }

    if (preferred !== null && availableKeys.has(preferred)) {
      nextKey = preferred;
    } else if (!availableKeys.has(currentKey)) {
      nextKey = normalized[0].categoryKey;
    }

    this.setData({
      categories: normalized,
      currentCategoryKey: nextKey,
    });
    return true;
  },

  bootstrapCategories() {
    const cache = squareDiscoveryService.getCategoriesCacheEntry();
    let categories: SquareCategoryCard[] = [];
    if (cache !== null && Array.isArray(cache.items) && cache.items.length > 0) {
      const age = Date.now() - cache.timestamp;
      const isFresh = age < SQUARE_CATEGORIES_CACHE_TTL_MS;
      const isStale =
        age < SQUARE_CATEGORIES_CACHE_TTL_MS + SQUARE_CATEGORIES_CACHE_STALE_PERIOD_MS;
      if (isFresh || isStale) {
        categories = cache.items;
      }
    }
    if (categories.length > 0) {
      this.applyCategories(categories, this._requestedCategoryKey, false);
      return;
    }
    this.setData({
      categories: [],
      contacts: [],
      hasMore: false,
      nextCursor: null,
      currentPageIndex: 1,
      maxPagesPerFeed: 1,
      endReason: null,
      ...buildPageLayoutScreenModelPayload({
        screenState: 'ready',
        contentVariant: 'data',
        refreshState: 'idle',
      }),
    });
  },

  async refreshCategories() {
    try {
      const result = await squareDiscoveryService.loadCategories();
      const preferredKey = this._requestedCategoryKey ?? this.data.currentCategoryKey;
      const applied = this.applyCategories(result.items, preferredKey, true);
      if (applied) {
        this._requestedCategoryKey = null;
      }
      return applied;
    } catch (error: unknown) {
      const err = normalizeError(error);
      logger.warn('Square categories refresh failed', { error: err.message });
      return true;
    }
  },

  filterRemovedContacts(contacts) {
    if (this._removedQiaoIds.size === 0) {
      return contacts;
    }
    return contacts.filter((item) => !this._removedQiaoIds.has(item.qiao_id));
  },

  async onLoad(options?: Record<string, string | undefined>) {
    this.squarePageService = createSquarePageService();
    const requestedCategory = options?.category_key;
    if (isNonEmptyString(requestedCategory)) {
      if (!isValidCategoryKey(requestedCategory)) {
        await this.switchToEntry('暂无内容');
        return;
      }
      this._requestedCategoryKey = requestedCategory;
    } else {
      this._requestedCategoryKey = null;
    }

    this._blankFailureToastShown = false;
    this._removedQiaoIds.clear();
    this.bootstrapCategories();
    await this.initializeOnce();
  },

  async ensureMinorModeAllowed() {
    const cached = getCachedMinorModeStatus();
    if (isMinorModeDiscoveryRestricted(cached)) {
      this.setData({
        minorModeDiscoveryBlocked: true,
        contacts: [],
        nextCursor: null,
        hasMore: true,
        currentPageIndex: 1,
        maxPagesPerFeed: 1,
        endReason: null,
        blankMessage: '青少年模式下 22:00-06:00 时段不可使用发现',
        ...buildPageLayoutScreenModelPayload(BLOCKED_SCREEN_MODEL),
      });
      return false;
    }
    try {
      const latest = await fetchMinorModeStatus();
      if (isMinorModeDiscoveryRestricted(latest)) {
        this.setData({
          minorModeDiscoveryBlocked: true,
          contacts: [],
          nextCursor: null,
          hasMore: true,
          currentPageIndex: 1,
          maxPagesPerFeed: 1,
          endReason: null,
          blankMessage: '青少年模式下 22:00-06:00 时段不可使用发现',
          ...buildPageLayoutScreenModelPayload(BLOCKED_SCREEN_MODEL),
        });
        return false;
      }
    } catch (error: unknown) {
      logger.warn('Failed to fetch minor mode status in square page', { error });
    }
    if (this.data.minorModeDiscoveryBlocked) {
      this.setData({
        minorModeDiscoveryBlocked: false,
        blankMessage: '页面暂时不可用，请稍后重试',
        ...buildPageLayoutScreenModelPayload({
          screenState: 'ready',
          contentVariant: 'data',
          refreshState: 'idle',
        }),
      });
    }
    return true;
  },

  async initializeOnce() {
    if (this._initialized) {
      this.startRefreshCountdown();
      return;
    }

    const passGuard = await requireAuth(this as unknown as AuthGuardPage);
    if (!passGuard) {
      return;
    }
    const allowed = await this.ensureMinorModeAllowed();
    if (!allowed) {
      this._initialized = true;
      return;
    }

    const categoriesReady = await this.refreshCategories();
    if (!categoriesReady) {
      return;
    }

    this._initialized = true;
    await this.loadContacts({
      mode: 'initial',
      showGlobalLoading: this.data.contacts.length === 0,
    });
  },

  async onShow() {
    if (this.data.minorModeDiscoveryBlocked) {
      const allowed = await this.ensureMinorModeAllowed();
      if (allowed) {
        this._initialized = false;
      }
    }
    await this.initializeOnce();
  },

  applyLoadingState(mode, showGlobalLoading) {
    this.setData({
      loading: mode !== 'load_more',
      loadingMore: mode === 'load_more',
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
  },

  async handleLoadResult(mode, result) {
    if (result === null) {
      this.setData({ loading: false, loadingMore: false });
      return true;
    }
    if (result.authInvalid) {
      this.setData({ loading: false, loadingMore: false });
      await showAuthExpiredModalAndRelogin();
      return true;
    }
    if (result.errorMessage.includes('无效的分类参数')) {
      this.setData({ loading: false, loadingMore: false });
      await this.switchToEntry('暂无内容');
      return true;
    }
    if (mode === 'load_more' && isNonEmptyString(result.errorMessage)) {
      showToast(result.errorMessage);
    }
    if (result.shouldToastBlankFailure) {
      const errorMessage = isNonEmptyString(result.errorMessage) ? result.errorMessage : '加载失败';
      this.notifyBlankLoadFailed(errorMessage);
    } else if (result.screenModel.contentVariant !== 'blank') {
      this._blankFailureToastShown = false;
    }
    return false;
  },

  applyFinalLoadResult(result) {
    const filteredContacts = this.filterRemovedContacts(result.contacts);
    const contentVariant =
      result.screenModel.contentVariant === 'blank'
        ? 'blank'
        : filteredContacts.length === 0
          ? 'empty'
          : 'data';

    this.setData({
      loading: false,
      loadingMore: false,
      ...(contentVariant === 'blank' ? null : { contacts: filteredContacts }),
      nextCursor: result.nextCursor,
      hasMore: result.hasMore,
      currentPageIndex: result.currentPageIndex,
      maxPagesPerFeed: result.maxPagesPerFeed,
      endReason: result.endReason,
      refreshRemainingSeconds: result.refreshRemainingSeconds,
      nextRefreshAvailableAt: result.nextRefreshAvailableAt,
      refreshIntervalSeconds: result.refreshIntervalSeconds,
      ...buildPageLayoutScreenModelPayload({
        ...result.screenModel,
        contentVariant,
      }),
    });
    this.updateRefreshInfoBar();
    this.startRefreshCountdown();
  },

  async loadContacts(options: LoadContactsOptions = {}) {
    const { mode = 'initial', showGlobalLoading = mode !== 'load_more' } = options;

    if (mode === 'load_more') {
      if (!this.data.hasMore || this.data.loadingMore || this.data.loading) {
        return;
      }
      if (!isNonEmptyString(this.data.nextCursor)) {
        return;
      }
    } else if (this.data.loading) {
      return;
    }

    if (!isValidCategoryKey(this.data.currentCategoryKey)) {
      await this.switchToEntry('暂无内容');
      return;
    }

    this.applyLoadingState(mode, showGlobalLoading);

    const result = await this.squarePageService.load(this.data.currentCategoryKey, {
      mode,
      hasCurrentContent: this.data.contacts.length > 0,
      currentContacts: this.data.contacts,
      currentCursor: this.data.nextCursor,
      hasMore: this.data.hasMore,
      currentNextRefreshAvailableAt: this.data.nextRefreshAvailableAt,
      currentRefreshIntervalSeconds: this.data.refreshIntervalSeconds,
    });

    const handled = await this.handleLoadResult(mode, result);
    if (handled || result === null) {
      return;
    }
    this.applyFinalLoadResult(result);
  },

  selectCategory(event) {
    if (this.data.minorModeDiscoveryBlocked) {
      return;
    }
    const categoryKey = toCategoryKey(getDatasetValue(event, 'categoryKey'));
    if (categoryKey === null || categoryKey === this.data.currentCategoryKey) {
      return;
    }

    const exists = this.data.categories.some((item) => item.categoryKey === categoryKey);
    if (!exists) {
      return;
    }

    this.setData({
      currentCategoryKey: categoryKey,
      contacts: [],
      nextCursor: null,
      hasMore: true,
      currentPageIndex: 1,
      maxPagesPerFeed: 1,
      endReason: null,
      refreshRemainingSeconds: 0,
      nextRefreshAvailableAt: null,
      refreshIntervalSeconds: 0,
      refreshInfoText: '刷新信息加载中',
      ...buildPageLayoutScreenModelPayload({
        screenState: 'ready',
        contentVariant: 'data',
        refreshState: 'idle',
      }),
    });
    this.stopRefreshCountdown();
    void this.loadContacts({ mode: 'initial' });
  },

  handleContentReachBottom() {
    if (this.data.minorModeDiscoveryBlocked) {
      return;
    }
    void this.loadContacts({
      mode: 'load_more',
      showGlobalLoading: false,
    });
  },

  handleContactTap(event) {
    if (this.data.minorModeDiscoveryBlocked) {
      return;
    }
    const qiaoId = toStringValue(getDatasetValue(event, 'id'));
    if (!isNonEmptyString(qiaoId)) {
      return;
    }

    const contact = this.data.contacts.find((item) => item.qiao_id === qiaoId) ?? null;
    const currentCategory =
      this.data.categories.find((item) => item.categoryKey === this.data.currentCategoryKey) ??
      null;

    void wx.navigateTo({
      url: `/pkg/stranger-info/stranger-info?id=${qiaoId}`,
      success: (res) => {
        res.eventChannel.on('contact-request-sent', (payload: ContactRequestSentPayload) => {
          this.handleStrangerContactRequestSent(payload);
        });

        if (contact === null) {
          return;
        }
        const payload: StrangerEntryPayload = {
          qiaoId: contact.qiao_id,
          nickname: contact.nickname,
          avatarUrl: contact.avatar_url,
          gender: contact.gender,
          categoryKey: this.data.currentCategoryKey,
          categoryTitle: currentCategory?.label,
          tags: contact.tags,
          remark: contact.remark,
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

  handleStrangerContactRequestSent(payload) {
    const qiaoId = isNonEmptyString(payload.qiaoId) ? payload.qiaoId.trim() : '';
    if (!isNonEmptyString(qiaoId)) {
      return;
    }
    this._removedQiaoIds.add(qiaoId);
    this.removeContactFromCurrentView(qiaoId);
  },

  removeContactFromCurrentView(qiaoId) {
    const updatedContacts = this.data.contacts.filter((contact) => contact.qiao_id !== qiaoId);
    this.setData({
      contacts: updatedContacts,
      ...buildPageLayoutScreenModelPayload({
        screenState: 'ready',
        contentVariant: updatedContacts.length === 0 ? 'empty' : 'data',
        refreshState: this.data.pageLayoutData.screenModel.refreshState,
      }),
    });
  },

  formatRefreshInfoText() {
    const nextRefreshAt = this.data.nextRefreshAvailableAt;
    if (nextRefreshAt === null) {
      return '刷新信息加载中';
    }
    const now = Date.now();
    const remainSeconds = Math.max(0, Math.ceil((nextRefreshAt - now) / 1000));
    if (remainSeconds <= 0) {
      return '当前分类可刷新';
    }
    return `下次刷新 ${formatTimestamp(nextRefreshAt)} · 还有 ${formatDuration(remainSeconds)}`;
  },

  updateRefreshInfoBar() {
    this.setData({
      refreshInfoText: this.formatRefreshInfoText(),
    });
  },

  startRefreshCountdown() {
    this.stopRefreshCountdown();
    if (this.data.nextRefreshAvailableAt === null) {
      return;
    }
    this._refreshCountdownTimer = setInterval(() => {
      this.updateRefreshInfoBar();
    }, 1000) as unknown as number;
  },

  stopRefreshCountdown() {
    if (this._refreshCountdownTimer === null) {
      return;
    }
    clearInterval(this._refreshCountdownTimer);
    this._refreshCountdownTimer = null;
  },

  onHide() {
    this.stopRefreshCountdown();
  },

  onUnload() {
    this.stopRefreshCountdown();
    this.squarePageService.dispose();
  },

  async handleAddContact(event) {
    if (this.data.minorModeDiscoveryBlocked) {
      return;
    }
    const qiaoId = toStringValue(getDatasetValue(event, 'id'));
    if (!isNonEmptyString(qiaoId)) {
      return;
    }
    const message = await promptContactRequestMessage();
    if (message === null) {
      return;
    }

    void wx.showLoading({ title: '发送中...', mask: true });

    try {
      await sendContactRequest({
        qiaoId,
        message,
        categoryKey: this.data.currentCategoryKey,
      });

      void wx.hideLoading();
      showToast('请求已发送', 'success');

      this._removedQiaoIds.add(qiaoId);
      this.removeContactFromCurrentView(qiaoId);

      logger.info('Contact request sent', {
        to_qiao_id: qiaoId,
        category_key: this.data.currentCategoryKey,
      });
    } catch (error) {
      const err = normalizeError(error);
      void wx.hideLoading();
      const failureMessage = isNonEmptyString(err.message) ? err.message : '发送失败';
      showToast(failureMessage);
      logger.error('Failed to send contact request', {
        to_qiao_id: qiaoId,
        error: failureMessage,
      });
    }
  },
});
