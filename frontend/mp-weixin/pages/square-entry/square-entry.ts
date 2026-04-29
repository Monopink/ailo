import { createPageLayoutData, type PageLayoutData } from '../../templates/page-layout';
import { type ScreenModel } from '../../services/pages/page-state';
import { requireAuth } from '../../utils/auth-guard';
import {
  SQUARE_CATEGORIES_CACHE_STALE_PERIOD_MS,
  SQUARE_CATEGORIES_CACHE_TTL_MS,
} from '../../utils/discovery-service';
import squareDiscoveryService from '../../utils/discovery-service';
import { isValidCategoryKey, type SquareCategoryCard } from '../../utils/constants/square';
import { getLogger } from '../../utils/logger';
import {
  fetchMinorModeStatus,
  getCachedMinorModeStatus,
  isMinorModeDiscoveryRestricted,
} from '../../utils/minor-mode';
import { initTabBar } from '../../utils/tab-bar';

const logger = getLogger('SquareEntry');

type AuthGuardPage = WechatMiniprogram.Page.Instance<
  Record<string, unknown>,
  Record<string, unknown>
>;

const showToast = (title: string): void => {
  void wx.showToast({ title, icon: 'none' });
};

const BLOCKED_SCREEN_MODEL: ScreenModel = {
  screenState: 'ready',
  contentVariant: 'blank',
  refreshState: 'idle',
};

interface SquareEntryPageData {
  pageLayoutData: PageLayoutData;
  entryCards: SquareCategoryCard[];
  categoriesReady: boolean;
  minorModeDiscoveryBlocked: boolean;
}

interface SquareEntryPageCustom {
  _navigating: boolean;
  checkMinorModeDiscoveryBlocked(): Promise<boolean>;
  applyScreenModel(screenModel: ScreenModel): void;
  bootstrapCategories(): void;
  refreshCategories(): Promise<void>;
  handleCardTap(event: WechatMiniprogram.TouchEvent): void;
}

const buildPageLayoutScreenModelPayload = (screenModel: ScreenModel): Record<string, unknown> => ({
  'pageLayoutData.screenModel': screenModel,
});

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

Page<SquareEntryPageData, SquareEntryPageCustom>({
  data: {
    pageLayoutData: createPageLayoutData({
      screenModel: {
        screenState: 'ready',
        contentVariant: 'data',
        refreshState: 'idle',
      },
      hasFooter: false,
    }),
    entryCards: squareDiscoveryService.getFallbackCategories(),
    categoriesReady: false,
    minorModeDiscoveryBlocked: false,
  },

  _navigating: false,

  applyScreenModel(screenModel) {
    this.setData(buildPageLayoutScreenModelPayload(screenModel));
  },

  bootstrapCategories() {
    const cache = squareDiscoveryService.getCategoriesCacheEntry();
    if (cache === null || !Array.isArray(cache.items) || cache.items.length === 0) {
      this.setData({
        entryCards: squareDiscoveryService.getFallbackCategories(),
        categoriesReady: false,
      });
      this.applyScreenModel({
        screenState: 'ready',
        contentVariant: 'data',
        refreshState: 'idle',
      });
      return;
    }

    const age = Date.now() - cache.timestamp;
    const isFresh = age < SQUARE_CATEGORIES_CACHE_TTL_MS;
    const isStale = age < SQUARE_CATEGORIES_CACHE_TTL_MS + SQUARE_CATEGORIES_CACHE_STALE_PERIOD_MS;
    if (!isFresh && !isStale) {
      this.setData({
        entryCards: squareDiscoveryService.getFallbackCategories(),
        categoriesReady: false,
      });
      return;
    }

    this.setData({ entryCards: cache.items, categoriesReady: cache.isFallback === false });
    this.applyScreenModel({
      screenState: 'ready',
      contentVariant: 'data',
      refreshState: isFresh ? 'idle' : 'degraded',
    });
  },

  async refreshCategories() {
    try {
      const result = await squareDiscoveryService.loadCategories();
      this.setData({ entryCards: result.items, categoriesReady: !result.isFallback });
      this.applyScreenModel({
        screenState: 'ready',
        contentVariant: 'data',
        refreshState: 'idle',
      });
    } catch (error: unknown) {
      logger.warn('Failed to refresh square categories', { error });
      this.setData({ categoriesReady: false });
    }
  },

  async checkMinorModeDiscoveryBlocked() {
    const cached = getCachedMinorModeStatus();
    if (isMinorModeDiscoveryRestricted(cached)) {
      this.setData({
        minorModeDiscoveryBlocked: true,
        categoriesReady: false,
      });
      this.applyScreenModel(BLOCKED_SCREEN_MODEL);
      return true;
    }
    try {
      const latest = await fetchMinorModeStatus();
      const blocked = isMinorModeDiscoveryRestricted(latest);
      this.setData({
        minorModeDiscoveryBlocked: blocked,
        categoriesReady: blocked ? false : this.data.categoriesReady,
      });
      if (blocked) {
        this.applyScreenModel(BLOCKED_SCREEN_MODEL);
      }
      return blocked;
    } catch (error: unknown) {
      logger.warn('Failed to fetch minor mode status in square-entry', { error });
      return false;
    }
  },

  async onShow() {
    initTabBar(this);
    const passGuard = await requireAuth(this as unknown as AuthGuardPage);
    if (!passGuard) {
      return;
    }
    const blocked = await this.checkMinorModeDiscoveryBlocked();
    if (blocked) {
      return;
    }
    if (this.data.minorModeDiscoveryBlocked) {
      this.setData({ minorModeDiscoveryBlocked: false });
    }
    this.bootstrapCategories();
    void this.refreshCategories();
  },

  handleCardTap(event) {
    if (this.data.minorModeDiscoveryBlocked) {
      return;
    }
    if (this._navigating) {
      showToast('暂无内容');
      return;
    }
    if (!this.data.categoriesReady) {
      showToast('暂无内容');
      return;
    }
    const categoryKey = toCategoryKey(getDatasetValue(event, 'categoryKey'));
    if (categoryKey === null) {
      showToast('暂无内容');
      return;
    }
    this._navigating = true;
    void wx.navigateTo({
      url: `/pkg/square/square?category_key=${encodeURIComponent(categoryKey)}`,
      fail: (error) => {
        logger.warn('Square entry navigation failed', { error, categoryKey });
        showToast('暂无内容');
      },
      complete: () => {
        this._navigating = false;
      },
    });
  },
});
