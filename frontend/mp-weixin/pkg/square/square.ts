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
import { createSquarePageService } from '../services/pages/square-service';

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
  feedVersion: string | null;
  nextCursor: string | null;
  hasMore: boolean;
  nextRefreshAvailableAt: number | null;
  minorModeDiscoveryBlocked: boolean;
}

interface LoadContactsOptions {
  mode?: 'initial' | 'refresh' | 'load_more';
  respectCooldown?: boolean;
  silentOnCooldown?: boolean;
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

interface SquarePageCustom {
  squarePageService: ReturnType<typeof createSquarePageService>;
  _blankFailureToastShown: boolean;
  _requestedCategoryKey: string | null;
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
  displayCachedContacts(): boolean;
  loadContactsWithCache(): void;
  revalidateCache(): Promise<void>;
  canStartLoad(
    mode: 'initial' | 'refresh' | 'load_more',
    respectCooldown: boolean,
    silentOnCooldown: boolean
  ): Promise<boolean>;
  applyLoadingState(mode: 'initial' | 'refresh' | 'load_more', showGlobalLoading: boolean): void;
  handleLoadResult(
    mode: 'initial' | 'refresh' | 'load_more',
    silentOnCooldown: boolean,
    result: Awaited<ReturnType<ReturnType<typeof createSquarePageService>['load']>>
  ): Promise<boolean>;
  applyFinalLoadResult(
    result: NonNullable<Awaited<ReturnType<ReturnType<typeof createSquarePageService>['load']>>>
  ): void;
  loadContacts(options?: LoadContactsOptions): Promise<void>;
  canRefreshNow(): boolean;
  getRefreshWaitSeconds(): number;
  selectCategory(event: WechatMiniprogram.TouchEvent): void;
  onPullDownRefresh(): void;
  onReachBottom(): void;
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
    feedVersion: null,
    nextCursor: null,
    hasMore: true,
    nextRefreshAvailableAt: null,
    minorModeDiscoveryBlocked: false,
  },

  _blankFailureToastShown: false,
  _requestedCategoryKey: null,
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
      void this.switchToEntry('暂无内容');
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
    const fallback = squareDiscoveryService.getFallbackCategories();
    let categories = fallback;
    if (cache !== null && Array.isArray(cache.items) && cache.items.length > 0) {
      const age = Date.now() - cache.timestamp;
      const isFresh = age < SQUARE_CATEGORIES_CACHE_TTL_MS;
      const isStale =
        age < SQUARE_CATEGORIES_CACHE_TTL_MS + SQUARE_CATEGORIES_CACHE_STALE_PERIOD_MS;
      if (isFresh || isStale) {
        categories = cache.items;
      }
    }
    this.applyCategories(categories, this._requestedCategoryKey, false);
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

  onLoad(options?: Record<string, string | undefined>) {
    this.squarePageService = createSquarePageService();
    const requestedCategory = options?.category_key;
    if (isNonEmptyString(requestedCategory)) {
      if (!isValidCategoryKey(requestedCategory)) {
        void this.switchToEntry('暂无内容');
        return;
      }
      this._requestedCategoryKey = requestedCategory;
    } else {
      this._requestedCategoryKey = null;
    }

    this._blankFailureToastShown = false;
    this.bootstrapCategories();
  },

  async ensureMinorModeAllowed() {
    const cached = getCachedMinorModeStatus();
    if (isMinorModeDiscoveryRestricted(cached)) {
      this.setData({
        minorModeDiscoveryBlocked: true,
        contacts: [],
        feedVersion: null,
        nextCursor: null,
        hasMore: true,
        nextRefreshAvailableAt: null,
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
          feedVersion: null,
          nextCursor: null,
          hasMore: true,
          nextRefreshAvailableAt: null,
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
        ...buildPageLayoutScreenModelPayload({
          screenState: 'ready',
          contentVariant: 'data',
          refreshState: 'idle',
        }),
      });
    }
    return true;
  },

  async onShow() {
    const isAuth = await requireAuth(this as unknown as AuthGuardPage);
    if (!isAuth) {
      return;
    }
    const allowed = await this.ensureMinorModeAllowed();
    if (!allowed) {
      return;
    }

    const categoriesReady = await this.refreshCategories();
    if (!categoriesReady) {
      return;
    }

    void this.loadContacts({
      mode: 'initial',
      respectCooldown: false,
      silentOnCooldown: true,
      showGlobalLoading: this.data.contacts.length === 0,
    });
  },

  displayCachedContacts() {
    const cacheResult = this.squarePageService.resolveCache(this.data.currentCategoryKey);
    if (cacheResult === null) {
      return false;
    }
    this.setData({
      contacts: cacheResult.contacts,
      feedVersion: cacheResult.feedVersion,
      nextCursor: cacheResult.nextCursor,
      hasMore: cacheResult.hasMore,
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
        mode: 'initial',
        respectCooldown: false,
        silentOnCooldown: true,
        showGlobalLoading: false,
      });
    } catch (error) {
      const err = normalizeError(error);
      logger.warn('Revalidation failed, keeping stale cache', { error: err.message });
    }
  },

  async canStartLoad(mode, respectCooldown, silentOnCooldown) {
    if (mode === 'refresh' && respectCooldown && !this.canRefreshNow()) {
      if (!silentOnCooldown) {
        const waitSeconds = this.getRefreshWaitSeconds();
        showToast(waitSeconds > 0 ? `请${waitSeconds}秒后再试` : '还不能刷新');
      }
      return false;
    }
    if (mode === 'load_more') {
      if (!this.data.hasMore || this.data.loadingMore || this.data.loading) {
        return false;
      }
    } else if (this.data.loading) {
      return false;
    }
    if (!isValidCategoryKey(this.data.currentCategoryKey)) {
      await this.switchToEntry('暂无内容');
      return false;
    }
    return true;
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

  async handleLoadResult(mode, silentOnCooldown, result) {
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
    if (mode === 'load_more' && isNonEmptyString(result.errorMessage) && !silentOnCooldown) {
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
    this.setData({
      loading: false,
      loadingMore: false,
      ...(result.screenModel.contentVariant === 'blank' ? null : { contacts: result.contacts }),
      feedVersion: result.feedVersion,
      nextCursor: result.nextCursor,
      hasMore: result.hasMore,
      nextRefreshAvailableAt: result.nextRefreshAvailableAt,
      ...buildPageLayoutScreenModelPayload(result.screenModel),
    });
  },

  async loadContacts(options: LoadContactsOptions = {}) {
    const {
      mode = 'initial',
      respectCooldown = mode === 'refresh',
      silentOnCooldown = false,
      showGlobalLoading = mode !== 'load_more',
    } = options;

    const canStart = await this.canStartLoad(mode, respectCooldown, silentOnCooldown);
    if (!canStart) {
      return;
    }
    this.applyLoadingState(mode, showGlobalLoading);

    const result = await this.squarePageService.load(this.data.currentCategoryKey, {
      mode,
      hasCurrentContent: this.data.contacts.length > 0,
      currentContacts: this.data.contacts,
      currentFeedVersion: this.data.feedVersion,
      currentCursor: this.data.nextCursor,
      hasMore: this.data.hasMore,
    });
    const handled = await this.handleLoadResult(mode, silentOnCooldown, result);
    if (handled || result === null) {
      return;
    }
    this.applyFinalLoadResult(result);
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
      feedVersion: null,
      nextCursor: null,
      hasMore: true,
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
    void this.loadContacts({ mode: 'refresh' }).finally(() => {
      void wx.stopPullDownRefresh();
    });
  },

  onReachBottom() {
    if (this.data.minorModeDiscoveryBlocked) {
      return;
    }
    void this.loadContacts({
      mode: 'load_more',
      respectCooldown: false,
      silentOnCooldown: true,
      showGlobalLoading: false,
    });
  },

  onUnload() {
    this.squarePageService.dispose();
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

  async handleAddContact(event) {
    if (this.data.minorModeDiscoveryBlocked) {
      return;
    }
    const qiaoId = toStringValue(getDatasetValue(event, 'id'));
    if (!isNonEmptyString(qiaoId)) {
      return;
    }
    const targetContact = this.data.contacts.find((item) => item.qiao_id === qiaoId) ?? null;
    const originalContacts = [...this.data.contacts];
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
        alias: targetContact?.nickname,
      });

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

      squareDiscoveryService.clearCache(this.data.currentCategoryKey);

      void this.loadContacts({
        mode: 'refresh',
        silentOnCooldown: true,
        showGlobalLoading: false,
      }).catch((error) => {
        const err = normalizeError(error);
        logger.warn('Square page refresh failed after add contact', { error: err.message });
      });

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
      this.setData({ contacts: originalContacts });
    }
  },
});
