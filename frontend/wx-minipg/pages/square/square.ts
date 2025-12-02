import { get, post } from '../../utils/api';
import { requireAuth } from '../../utils/auth-guard';
import { getAvatarUrl } from '../../utils/avatar';
import logger from '../../utils/logger';

const CATEGORIES = [
  { key: null, label: '全部' },
  { key: 1, label: '交友' },
  { key: 2, label: '恋爱' },
  { key: 3, label: '倾诉' },
  { key: 4, label: '闺蜜' },
  { key: 5, label: '同好' }
];

const CACHE_TTL = 10 * 60 * 1000; // 10 minutes
const STALE_PERIOD = 60 * 60 * 1000; // 1 hour

Page({
  data: {
    categories: CATEGORIES,
    currentCategory: null,
    contacts: [],
    loading: false,
    page: 1,
    pageSize: 20,
    hasMore: true,
    loadingMore: false
  },

  async onLoad() {
    const isAuth = await requireAuth(this);
    if (!isAuth) return;
    this.loadContactsWithCache();
  },

  // Cache key for current category
  getCacheKey() {
    return `square_${this.data.currentCategory || 'all'}`;
  },

  // Load contacts with cache strategy
  async loadContactsWithCache() {
    const cacheKey = this.getCacheKey();
    const cache = wx.getStorageSync(cacheKey);
    const now = Date.now();

    if (cache && cache.timestamp) {
      const age = now - cache.timestamp;

      // Fresh cache (< 10 min): use directly
      if (age < CACHE_TTL) {
        this.setData({ contacts: cache.contacts, hasMore: cache.hasMore });
        logger.info('Using fresh cache', { age: Math.floor(age / 1000) });
        return;
      }

      // Stale cache (10 min - 1 hour): show cache, revalidate in background
      if (age < CACHE_TTL + STALE_PERIOD) {
        this.setData({ contacts: cache.contacts, hasMore: cache.hasMore });
        logger.info('Using stale cache, revalidating', { age: Math.floor(age / 1000) });
        this.revalidateCache(cacheKey);
        return;
      }
    }

    // No cache or expired: must fetch
    this.loadContacts(true);
  },

  // Background revalidation (silent)
  async revalidateCache(cacheKey) {
    try {
      const params = { page: 1, page_size: this.data.pageSize };
      if (this.data.currentCategory !== null) {
        params.category = this.data.currentCategory;
      }

      const result = await get('/discovery/square', params);
      const contacts = this.processContacts(result.items);

      // Save to cache
      wx.setStorageSync(cacheKey, {
        contacts,
        hasMore: result.pagination.has_more,
        timestamp: Date.now()
      });

      // Update UI silently
      this.setData({ contacts, hasMore: result.pagination.has_more });
      logger.info('Cache revalidated');
    } catch (error) {
      // Silent failure - keep using stale cache
      logger.warn('Revalidation failed, keeping stale cache', { error: error.message });
    }
  },

  // Load contacts from API
  async loadContacts(isRefresh = false) {
    if (this.data.loading) return;

    this.setData({ loading: true });

    try {
      const params = {
        page: isRefresh ? 1 : this.data.page,
        page_size: this.data.pageSize
      };

      if (this.data.currentCategory !== null) {
        params.category = this.data.currentCategory;
      }

      const result = await get('/discovery/square', params);
      const contacts = this.processContacts(result.items);

      this.setData({
        contacts: isRefresh ? contacts : [...this.data.contacts, ...contacts],
        page: isRefresh ? 2 : this.data.page + 1,
        hasMore: result.pagination.has_more,
        loading: false
      });

      // Save first page to cache
      if (isRefresh) {
        wx.setStorageSync(this.getCacheKey(), {
          contacts,
          hasMore: result.pagination.has_more,
          timestamp: Date.now()
        });
      }

      logger.info('Contacts loaded', {
        category: this.data.currentCategory,
        count: contacts.length
      });

    } catch (error) {
      this.setData({ loading: false });

      // Check if we have stale cache to fall back to
      const cache = wx.getStorageSync(this.getCacheKey());
      if (cache && cache.timestamp) {
        const age = Date.now() - cache.timestamp;

        // Within stale period: keep cache, no error
        if (age < CACHE_TTL + STALE_PERIOD) {
          logger.warn('Load failed, using stale cache', { age: Math.floor(age / 1000) });
          return;
        }
      }

      // No valid cache: show error and clear
      wx.removeStorageSync(this.getCacheKey());
      const errorMsg = error.message || '加载失败';
      if (!errorMsg.includes('频繁')) {
        wx.showToast({ title: errorMsg, icon: 'none' });
      }
      logger.error('Load failed', { error: errorMsg });
    }
  },

  // Process contacts data
  processContacts(items) {
    return (items || []).map(contact => ({
      id: contact.qiao_id,
      qiao_id: contact.qiao_id,
      nickname: contact.nickname,
      gender: contact.gender,
      avatar_url: getAvatarUrl(contact.avatar_url),
      bio: contact.bio,
      region: contact.region,
      category: contact.category
    }));
  },

  // Switch category
  selectCategory(e) {
    const category = e.currentTarget.dataset.category;
    const categoryValue = category === 'null' ? null : parseInt(category);

    if (categoryValue === this.data.currentCategory) return;

    this.setData({
      currentCategory: categoryValue,
      contacts: [],
      page: 1,
      hasMore: true
    });

    this.loadContactsWithCache();
  },

  // Pull down refresh
  onPullDownRefresh() {
    this.setData({
      contacts: [],
      page: 1,
      hasMore: true
    });

    this.loadContacts(true);
    wx.stopPullDownRefresh();
  },

  // Reach bottom - load more
  onReachBottom() {
    if (!this.data.hasMore || this.data.loading || this.data.loadingMore) return;

    this.setData({ loadingMore: true });
    this.loadContacts().finally(() => {
      this.setData({ loadingMore: false });
    });
  },

  // Navigate to contact detail
  handleContactTap(e) {
    const qiaoId = e.currentTarget.dataset.id;
    wx.navigateTo({
      url: `/pages/stranger-info/stranger-info?id=${qiaoId}`
    });
  },

  // Add contact
  async handleAddContact(e) {
    const qiaoId = e.currentTarget.dataset.id;

    wx.showLoading({ title: '发送中...', mask: true });

    try {
      await post('/contact-requests', {
        to_qiao_id: qiaoId,
        message: '你好，我想添加你为联系人'
      });

      wx.hideLoading();
      wx.showToast({ title: '请求已发送', icon: 'success' });

      logger.info('Contact request sent', { to_qiao_id: qiaoId });
    } catch (error) {
      wx.hideLoading();
      wx.showToast({
        title: error.message || '发送失败',
        icon: 'none'
      });

      logger.error('Failed to send contact request', {
        to_qiao_id: qiaoId,
        error: error.message || String(error)
      });
    }
  }
});
