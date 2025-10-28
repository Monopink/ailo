import { getAvatarUrl } from '../../utils/avatar';
import logger from '../../utils/logger';
import { getContacts, getStorage, setStorage } from '../../utils/storage';

const SEARCH_HISTORY_KEY = 'search_history';
const MAX_HISTORY_COUNT = 10;

Page({
  data: {
    searchKeyword: '',
    searchResults: [],
    searchHistory: [],
    showHistory: true,
    loading: false
  },

  async onLoad() {
    logger.info('Search page loaded');
    await this.loadSearchHistory();
  },

  async loadSearchHistory() {
    try {
      const history = await getStorage(SEARCH_HISTORY_KEY, []);
      this.setData({ searchHistory: history });
    } catch (error) {
      logger.error('Failed to load search history', { error });
    }
  },

  async saveSearchHistory(keyword) {
    try {
      let history = await getStorage(SEARCH_HISTORY_KEY, []);

      // Remove duplicate
      history = history.filter(item => item !== keyword);

      // Add to front
      history.unshift(keyword);

      // Limit count
      if (history.length > MAX_HISTORY_COUNT) {
        history = history.slice(0, MAX_HISTORY_COUNT);
      }

      await setStorage(SEARCH_HISTORY_KEY, history);
      this.setData({ searchHistory: history });
    } catch (error) {
      logger.error('Failed to save search history', { error });
    }
  },

  async clearSearchHistory() {
    try {
      await setStorage(SEARCH_HISTORY_KEY, []);
      this.setData({ searchHistory: [] });

      wx.showToast({
        title: '已清空',
        icon: 'success'
      });
    } catch (error) {
      logger.error('Failed to clear search history', { error });
    }
  },

  onSearchInput(e) {
    const keyword = e.detail.value;
    this.setData({ searchKeyword: keyword });

    if (keyword.trim()) {
      this.performSearch(keyword);
    } else {
      this.setData({
        searchResults: [],
        showHistory: true
      });
    }
  },

  onSearchConfirm(e) {
    const keyword = e.detail.value.trim();
    if (keyword) {
      this.performSearch(keyword);
      this.saveSearchHistory(keyword);
    }
  },

  async performSearch(keyword) {
    try {
      this.setData({ loading: true, showHistory: false });

      const contacts = await getContacts();
      const lowerKeyword = keyword.toLowerCase();

      // Filter contacts by keyword
      const results = contacts.filter(contact => {
        const displayName = (contact.alias || contact.nickname || contact.contact_qiao_id || '').toLowerCase();
        const remark = (contact.remark || '').toLowerCase();
        const qiaoId = (contact.contact_qiao_id || '').toLowerCase();

        return displayName.includes(lowerKeyword) ||
          remark.includes(lowerKeyword) ||
          qiaoId.includes(lowerKeyword);
      });

      // Process results
      const processedResults = results.map(contact => ({
        ...contact,
        avatarUrl: getAvatarUrl(contact.avatar_alias_url || contact.avatar_url),
        displayName: contact.alias || contact.nickname || contact.contact_qiao_id,
        lastMessageTime: this.formatTime(contact.last_message_time),
        lastMessageContent: contact.last_message_content || ''
      }));

      this.setData({
        searchResults: processedResults,
        loading: false
      });

      logger.info('Search completed', { keyword, count: processedResults.length });
    } catch (error) {
      logger.error('Search failed', { error });
      this.setData({ loading: false });

      wx.showToast({
        title: '搜索失败',
        icon: 'none'
      });
    }
  },

  onHistoryItemTap(e) {
    const keyword = e.currentTarget.dataset.keyword;
    this.setData({ searchKeyword: keyword });
    this.performSearch(keyword);
  },

  onClearHistory() {
    wx.showModal({
      title: '提示',
      content: '确定清空搜索历史吗？',
      success: (res) => {
        if (res.confirm) {
          this.clearSearchHistory();
        }
      }
    });
  },

  goToContactInfo(e) {
    const convId = e.currentTarget.dataset.id;
    wx.navigateTo({
      url: `/pages/contact-info/contact-info?id=${convId}`
    });
  },

  goToChat(e) {
    const convId = e.currentTarget.dataset.id;
    wx.navigateTo({
      url: `/pages/chat/chat?id=${convId}`
    });
  },

  formatTime(timestamp) {
    if (!timestamp) return '';

    const date = new Date(timestamp);
    const now = new Date();
    const diff = now - date;

    // Less than 1 minute
    if (diff < 60000) {
      return '刚刚';
    }

    // Less than 1 hour
    if (diff < 3600000) {
      return `${Math.floor(diff / 60000)}分钟前`;
    }

    // Less than 1 day
    if (diff < 86400000) {
      return `${Math.floor(diff / 3600000)}小时前`;
    }

    // Less than 7 days
    if (diff < 604800000) {
      return `${Math.floor(diff / 86400000)}天前`;
    }

    // Format as date
    return `${date.getMonth() + 1}月${date.getDate()}日`;
  }
});

