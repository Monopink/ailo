import { get } from '../../utils/api';
import { requireAuthForPage } from '../../utils/auth-guard';
import { getAvatarUrl } from '../../utils/avatar';
import logger from '../../utils/logger';

// Category mapping: filter name -> category number
const CATEGORY_MAP = {
  'friend': 1,  // 交友
  'love': 2,    // 恋爱
  'talk': 3,    // 倾诉
  'bestie': 4,  // 闺蜜
  'hobby': 5    // 同好
};

Page({
  data: {
    isLoggedIn: false,
    filterExpanded: true,
    currentFilter: 'friend',
    contacts: [],
    loading: false
  },

  onLoad(options) {
    // Enforce auth; redirect to welcome if not logged in
    if (!requireAuthForPage(this)) {
      return;
    }
    // Load cache first, then refresh
    this.loadContacts(false);
  },

  onShow() {
    // Enforce auth every time page shows
    if (!requireAuthForPage(this)) {
      return;
    }
    this.setData({ isLoggedIn: true });
  },

  // Auth status is enforced via requireAuthForPage; isLoggedIn kept for UI gates

  // Get cache key
  getCacheKey(category) {
    return `square_contacts_${category || 'all'}`;
  },

  // Save cache
  async saveCache(category, contacts) {
    const key = this.getCacheKey(category);
    const data = {
      contacts,
      timestamp: Date.now(),
      category
    };
    wx.setStorageSync(key, data);
    logger.info('Square cache saved', { category, count: contacts.length });
  },

  // Load cache
  async loadCache(category) {
    const key = this.getCacheKey(category);
    const cache = wx.getStorageSync(key) || null;
    if (cache) {
      logger.info('Square cache loaded', { category, count: cache.contacts.length });
    }
    return cache;
  },

  // Check cache validity (10 minutes)
  isCacheValid(cache) {
    if (!cache) return false;
    const elapsed = Date.now() - cache.timestamp;
    const isValid = elapsed < 10 * 60 * 1000;  // 10 minutes
    logger.debug('Square cache validity check', {
      elapsed_seconds: Math.floor(elapsed / 1000),
      is_valid: isValid
    });
    return isValid;
  },

  async loadContacts(isCategoryChange = false) {
    try {
      const category = CATEGORY_MAP[this.data.currentFilter];

      // 1. Try to load cache first
      const cache = await this.loadCache(category);
      if (this.isCacheValid(cache)) {
        this.setData({
          contacts: cache.contacts,
          loading: false
        });

        logger.info('Using cached contacts', { category, count: cache.contacts.length });

        // If not category change, return directly
        if (!isCategoryChange) {
          return;
        }
      }

      // 2. Show loading (if no cache, show loading; if has cache, refresh in background)
      if (!cache) {
        this.setData({ loading: true });
      }

      // 3. Request API
      const result = await get('/discovery/square', {
        category: category,
        force_refresh: false
      });

      // 4. Update data and cache
      const contacts = result.items.map(contact => ({
        id: contact.qiao_id,
        qiao_id: contact.qiao_id,
        nickname: contact.nickname,
        gender: contact.gender,
        avatar_url: getAvatarUrl(contact.avatar_url),
        bio: contact.bio,
        region: contact.region,
        category: contact.category
      }));

      this.setData({
        contacts,
        loading: false
      });

      // 5. Save cache
      await this.saveCache(category, contacts);

      logger.info('Contacts refreshed from API', { category, count: contacts.length });

    } catch (error) {
      logger.error('Failed to load contacts', { error });

      // If has cache, continue using cache
      if (cache) {
        this.setData({
          contacts: cache.contacts,
          loading: false
        });

        wx.showToast({
          title: '刷新失败,显示缓存数据',
          icon: 'none'
        });
      } else {
        this.setData({ loading: false });
        wx.showToast({
          title: '加载失败',
          icon: 'none'
        });
      }
    }
  },

  selectFilter(e) {
    const filter = e.currentTarget.dataset.filter;

    // Switch category
    this.setData({
      currentFilter: filter,
      filterExpanded: false
    });

    // Load data (mark as category change)
    this.loadContacts(true);
  },

  handleRefresh() {
    if (!this.data.isLoggedIn) {
      wx.showToast({ title: '请先登录', icon: 'none' });
      return;
    }
    this.loadContacts(true);
  },

  handleContactTap(e) {
    if (!this.data.isLoggedIn) {
      wx.showToast({ title: '请先登录', icon: 'none' });
      return;
    }

    const qiaoId = e.currentTarget.dataset.id;
    wx.navigateTo({
      url: `/pages/stranger-info/stranger-info?id=${qiaoId}`
    });
  },

  onPageScroll(e) {
    // Collapse filter bar on scroll up
    if (e.detail.scrollTop > 50 && this.data.filterExpanded) {
      this.setData({ filterExpanded: false });
    }
  }
});
