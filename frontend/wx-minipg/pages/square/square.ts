import { requireAuth } from '../../utils/auth-guard';
import { getLogger } from '../../utils/logger';
import { promptContactRequestMessage, sendContactRequest } from '../../utils/contact-request';
import squareDiscoveryService, {
  type SquareContactViewModel,
  SQUARE_CACHE_STALE_PERIOD_MS,
  SQUARE_CACHE_TTL_MS,
} from '../../utils/discovery-service';
import { createPageLayoutData, type PageLayoutData } from '../../templates/page-layout';
import { isNonEmptyString } from '../../utils/guards';
import { initTabBar } from '../../utils/tab-bar';

const logger = getLogger('Square');

const CATEGORIES = [
  { key: null, label: '全部' },
  { key: 1, label: '交友' },
  { key: 2, label: '恋爱' },
  { key: 3, label: '倾诉' },
  { key: 4, label: '闺蜜' },
  { key: 5, label: '同好' },
] as const;

type AuthGuardPage = WechatMiniprogram.Page.Instance<
  Record<string, unknown>,
  Record<string, unknown>
>;

interface CategoryItem {
  key: number | null;
  label: string;
}

interface SquarePageData {
  pageLayoutData: PageLayoutData;
  categories: readonly CategoryItem[];
  currentCategory: number | null;
  contacts: SquareContactViewModel[];
  loading: boolean;
  nextRefreshAvailableAt: number | null;
}

interface LoadContactsOptions {
  respectCooldown?: boolean;
  silentOnCooldown?: boolean;
  showGlobalLoading?: boolean;
}

interface SquarePageCustom {
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
  onRetry(): void;
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

const toCategoryValue = (value: unknown): number | null => {
  if (value === null || value === undefined) {
    return null;
  }
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === 'string') {
    if (value === 'null' || value === '') {
      return null;
    }
    const parsed = Number.parseInt(value, 10);
    return Number.isNaN(parsed) ? null : parsed;
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

Page<SquarePageData, SquarePageCustom>({
  data: {
    pageLayoutData: createPageLayoutData(),
    categories: CATEGORIES,
    currentCategory: null,
    contacts: [],
    loading: false,
    nextRefreshAvailableAt: null,
  },

  async onLoad() {
    const isAuth = await requireAuth(this as unknown as AuthGuardPage);
    if (!isAuth) {
      return;
    }
    this.loadContactsWithCache();
  },

  onShow() {
    initTabBar(this);
  },
  displayCachedContacts() {
    const cache = squareDiscoveryService.getCacheEntry(this.data.currentCategory);
    if (cache === null || typeof cache.timestamp !== 'number') {
      return false;
    }

    const age = Date.now() - cache.timestamp;
    this.setData({
      contacts: cache.contacts,
      nextRefreshAvailableAt: cache.nextRefreshAvailableAt,
      'pageLayoutData.isLoading': false,
      'pageLayoutData.hasError': false,
      'pageLayoutData.errorMessage': '',
      'pageLayoutData.isEmpty': cache.contacts.length === 0,
    });

    if (age < SQUARE_CACHE_TTL_MS) {
      logger.info('Using fresh cache', { age: Math.floor(age / 1000) });
      return true;
    }

    if (age < SQUARE_CACHE_TTL_MS + SQUARE_CACHE_STALE_PERIOD_MS) {
      logger.info('Using stale cache, revalidating', { age: Math.floor(age / 1000) });
      void this.revalidateCache();
      return true;
    }

    return false;
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

  onRetry() {
    this.setData({
      'pageLayoutData.hasError': false,
      'pageLayoutData.isLoading': true,
    });
    void this.loadContacts({ respectCooldown: false, showGlobalLoading: true });
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
            'pageLayoutData.isLoading': true,
            'pageLayoutData.hasError': false,
          }
        : null),
    });

    try {
      const result = await squareDiscoveryService.load(this.data.currentCategory);
      this.setData({
        contacts: result.contacts,
        nextRefreshAvailableAt: result.nextRefreshAvailableAt,
        'pageLayoutData.isLoading': false,
        'pageLayoutData.hasError': false,
        'pageLayoutData.isEmpty': result.contacts.length === 0,
        'pageLayoutData.errorMessage': '',
      });

      logger.info('Contacts loaded', {
        category: this.data.currentCategory,
        count: result.contacts.length,
      });
    } catch (error) {
      const err = normalizeError(error);
      this.setData({
        'pageLayoutData.isLoading': false,
      });

      const cache = squareDiscoveryService.getCacheEntry(this.data.currentCategory);
      if (cache !== null && typeof cache.timestamp === 'number') {
        const age = Date.now() - cache.timestamp;
        if (age < SQUARE_CACHE_TTL_MS + SQUARE_CACHE_STALE_PERIOD_MS) {
          logger.warn('Load failed, using stale cache', { age: Math.floor(age / 1000) });
          this.setData({
            contacts: cache.contacts,
            nextRefreshAvailableAt: cache.nextRefreshAvailableAt,
            'pageLayoutData.isEmpty': cache.contacts.length === 0,
            'pageLayoutData.hasError': false,
            'pageLayoutData.errorMessage': '',
          });
          return;
        }
      }

      const errorMessage = isNonEmptyString(err.message) ? err.message : '加载失败';
      showToast(errorMessage);
      this.setData({
        'pageLayoutData.hasError': true,
        'pageLayoutData.errorMessage': errorMessage,
      });
      logger.error('Load failed', { error: err.message });
    } finally {
      this.setData({ loading: false });
    }
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
    const category = toCategoryValue(getDatasetValue(event, 'category'));
    if (category === this.data.currentCategory) {
      return;
    }

    this.setData({
      currentCategory: category,
      contacts: [],
      nextRefreshAvailableAt: null,
      'pageLayoutData.isEmpty': false,
    });

    this.loadContactsWithCache();
  },

  onPullDownRefresh() {
    void this.loadContacts().finally(() => {
      void wx.stopPullDownRefresh();
    });
  },

  handleContactTap(event) {
    const qiaoId = toStringValue(getDatasetValue(event, 'id'));
    if (!isNonEmptyString(qiaoId)) {
      return;
    }

    void wx.navigateTo({
      url: `/pages/stranger-info/stranger-info?id=${qiaoId}`,
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
        'pageLayoutData.isEmpty': updatedContacts.length === 0,
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
