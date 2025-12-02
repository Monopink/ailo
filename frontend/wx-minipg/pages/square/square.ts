import { get } from '../../utils/api';
import { requireAuth } from '../../utils/auth-guard';
import { getAvatarUrl } from '../../utils/avatar';
import { getLogger } from '../../utils/logger';
import { promptContactRequestMessage, sendContactRequest } from '../../utils/contact-request';

const logger = getLogger('Square');

const CATEGORIES = [
  { key: null, label: '全部' },
  { key: 1, label: '交友' },
  { key: 2, label: '恋爱' },
  { key: 3, label: '倾诉' },
  { key: 4, label: '闺蜜' },
  { key: 5, label: '同好' },
] as const;

const CACHE_TTL = 10 * 60 * 1000; // 10 minutes
const STALE_PERIOD = 60 * 60 * 1000; // 1 hour

type AuthGuardPage = WechatMiniprogram.Page.Instance<
  Record<string, unknown>,
  Record<string, unknown>
>;

interface CategoryItem {
  key: number | null;
  label: string;
}

interface SquareContact {
  id: string;
  qiao_id: string;
  nickname?: string;
  gender?: number | null;
  avatar_url?: string;
  bio?: string;
  region?: string;
  category?: number | null;
}

interface SquareApiContact {
  qiao_id: string;
  nickname?: string;
  gender?: number | null;
  avatar_url?: string;
  bio?: string;
  region?: string;
  category?: number | null;
}

interface SquareApiResponse {
  items: SquareApiContact[];
  pagination: {
    has_more: boolean;
  };
}

interface CacheEntry {
  contacts: SquareContact[];
  hasMore: boolean;
  timestamp: number;
}

interface SquarePageData {
  categories: readonly CategoryItem[];
  currentCategory: number | null;
  contacts: SquareContact[];
  loading: boolean;
  page: number;
  pageSize: number;
  hasMore: boolean;
  loadingMore: boolean;
}

interface SquarePageCustom {
  getCacheKey(): string;
  loadContactsWithCache(): void;
  revalidateCache(cacheKey: string): Promise<void>;
  loadContacts(isRefresh?: boolean): Promise<void>;
  processContacts(items: SquareApiContact[] | undefined): SquareContact[];
  selectCategory(event: WechatMiniprogram.TouchEvent): void;
  onPullDownRefresh(): void;
  onReachBottom(): void;
  handleContactTap(event: WechatMiniprogram.BaseEvent): void;
  handleAddContact(event: WechatMiniprogram.BaseEvent): Promise<void>;
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
  const dataset = event?.currentTarget?.dataset as Record<string, unknown> | undefined;
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
    categories: CATEGORIES,
    currentCategory: null,
    contacts: [],
    loading: false,
    page: 1,
    pageSize: 20,
    hasMore: true,
    loadingMore: false,
  },

  async onLoad() {
    const isAuth = await requireAuth(this as unknown as AuthGuardPage);
    if (!isAuth) {
      return;
    }
    this.loadContactsWithCache();
  },

  getCacheKey() {
    const category = this.data.currentCategory;
    return `square_${category ?? 'all'}`;
  },

  loadContactsWithCache() {
    const cacheKey = this.getCacheKey();
    const cache = wx.getStorageSync<CacheEntry | null>(cacheKey);
    const now = Date.now();

    if (cache && typeof cache.timestamp === 'number') {
      const age = now - cache.timestamp;

      if (age < CACHE_TTL) {
        this.setData({ contacts: cache.contacts, hasMore: cache.hasMore });
        logger.info('Using fresh cache', { age: Math.floor(age / 1000) });
        return;
      }

      if (age < CACHE_TTL + STALE_PERIOD) {
        this.setData({ contacts: cache.contacts, hasMore: cache.hasMore });
        logger.info('Using stale cache, revalidating', { age: Math.floor(age / 1000) });
        void this.revalidateCache(cacheKey);
        return;
      }
    }

    void this.loadContacts(true);
  },

  async revalidateCache(cacheKey) {
    try {
      const params: Record<string, number> = { page: 1, page_size: this.data.pageSize };
      if (this.data.currentCategory !== null) {
        params.category = this.data.currentCategory;
      }

      const result = await get<SquareApiResponse>('/discovery/square', params);
      const contacts = this.processContacts(result.items);

      const cacheEntry: CacheEntry = {
        contacts,
        hasMore: result.pagination?.has_more ?? false,
        timestamp: Date.now(),
      };
      wx.setStorageSync(cacheKey, cacheEntry);

      this.setData({ contacts, hasMore: result.pagination?.has_more ?? false });
      logger.info('Cache revalidated');
    } catch (error) {
      const err = normalizeError(error);
      logger.warn('Revalidation failed, keeping stale cache', { error: err.message });
    }
  },

  async loadContacts(isRefresh = false) {
    if (this.data.loading) {
      return;
    }

    this.setData({ loading: true });

    try {
      const params: Record<string, number> = {
        page: isRefresh ? 1 : this.data.page,
        page_size: this.data.pageSize,
      };

      if (this.data.currentCategory !== null) {
        params.category = this.data.currentCategory;
      }

      const result = await get<SquareApiResponse>('/discovery/square', params);
      const contacts = this.processContacts(result.items);
      const hasMore = result.pagination?.has_more ?? false;

      this.setData({
        contacts: isRefresh ? contacts : [...this.data.contacts, ...contacts],
        page: isRefresh ? 2 : this.data.page + 1,
        hasMore,
        loading: false,
      });

      if (isRefresh) {
        const cacheEntry: CacheEntry = {
          contacts,
          hasMore,
          timestamp: Date.now(),
        };
        wx.setStorageSync(this.getCacheKey(), cacheEntry);
      }

      logger.info('Contacts loaded', {
        category: this.data.currentCategory,
        count: contacts.length,
      });
    } catch (error) {
      const err = normalizeError(error);
      this.setData({ loading: false });

      const cache = wx.getStorageSync<CacheEntry | null>(this.getCacheKey());
      if (cache && typeof cache.timestamp === 'number') {
        const age = Date.now() - cache.timestamp;
        if (age < CACHE_TTL + STALE_PERIOD) {
          logger.warn('Load failed, using stale cache', { age: Math.floor(age / 1000) });
          return;
        }
      }

      wx.removeStorageSync(this.getCacheKey());
      if (!err.message.includes('频繁')) {
        showToast(err.message || '加载失败');
      }
      logger.error('Load failed', { error: err.message });
    }
  },

  processContacts(items) {
    return (items ?? []).map((contact) => ({
      id: contact.qiao_id,
      qiao_id: contact.qiao_id,
      nickname: contact.nickname,
      gender: contact.gender ?? null,
      avatar_url: getAvatarUrl(contact.avatar_url ?? ''),
      bio: contact.bio,
      region: contact.region,
      category: contact.category ?? null,
    }));
  },

  selectCategory(event) {
    const category = toCategoryValue(getDatasetValue(event, 'category'));
    if (category === this.data.currentCategory) {
      return;
    }

    this.setData({
      currentCategory: category,
      contacts: [],
      page: 1,
      hasMore: true,
    });

    this.loadContactsWithCache();
  },

  onPullDownRefresh() {
    this.setData({
      contacts: [],
      page: 1,
      hasMore: true,
    });

    void this.loadContacts(true);
    void wx.stopPullDownRefresh();
  },

  onReachBottom() {
    if (!this.data.hasMore || this.data.loading || this.data.loadingMore) {
      return;
    }

    this.setData({ loadingMore: true });
    void this.loadContacts().finally(() => {
      this.setData({ loadingMore: false });
    });
  },

  handleContactTap(event) {
    const qiaoId = toStringValue(getDatasetValue(event, 'id'));
    if (!qiaoId) {
      return;
    }

    void wx.navigateTo({
      url: `/pages/stranger-info/stranger-info?id=${qiaoId}`,
    });
  },

  async handleAddContact(event) {
    const qiaoId = toStringValue(getDatasetValue(event, 'id'));
    if (!qiaoId) {
      return;
    }

    const originalContacts = this.data.contacts ?? [];
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
        page: 1,
        hasMore: true,
      });

      const cacheKey = this.getCacheKey();
      wx.removeStorageSync(cacheKey);

      void this.loadContacts(true).catch((error) => {
        const err = normalizeError(error);
        logger.warn('Square page refresh failed after add contact', { error: err.message });
      });

      logger.info('Contact request sent', { to_qiao_id: qiaoId });
    } catch (error) {
      const err = normalizeError(error);
      void wx.hideLoading();
      showToast(err.message || '发送失败');
      logger.error('Failed to send contact request', { to_qiao_id: qiaoId, error: err.message });
      this.setData({ contacts: originalContacts });
    }
  },
});
