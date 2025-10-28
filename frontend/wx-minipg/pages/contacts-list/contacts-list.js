import { getAvatarUrl } from '../../utils/avatar';
import logger from '../../utils/logger';
import { getContacts } from '../../utils/storage';

Page({
  data: {
    contacts: [],
    groupedContacts: [],
    searchKeyword: '',
    loading: false
  },

  onLoad() {
    logger.info('Contacts list page loaded');
    this.loadContacts();
  },

  onShow() {
    // Reload contacts when page shows
    this.loadContacts();
  },

  async loadContacts() {
    if (this.data.loading) return;

    try {
      this.setData({ loading: true });

      // Load from local storage
      const contacts = await getContacts();
      this.updateContactsList(contacts);
    } catch (error) {
      logger.error('Failed to load contacts', {
        error: error.message || String(error)
      });

      this.setData({ loading: false });

      wx.showToast({
        title: '加载失败',
        icon: 'none'
      });
    }
  },

  updateContactsList(contacts) {
    // Process contacts
    const processedContacts = contacts.map(contact => ({
      ...contact,
      avatarUrl: getAvatarUrl(contact.avatar_alias_url || contact.avatar_url),
      displayName: contact.alias || contact.nickname || contact.contact_qiao_id,
      lastActiveTime: this.formatTime(contact.last_message_time)
    }));

    // Group contacts by first letter
    const groupedContacts = this.groupContactsByLetter(processedContacts);

    this.setData({
      contacts: processedContacts,
      groupedContacts,
      loading: false
    });
  },

  groupContactsByLetter(contacts) {
    // Filter by search keyword
    let filteredContacts = contacts;
    if (this.data.searchKeyword) {
      const keyword = this.data.searchKeyword.toLowerCase();
      filteredContacts = contacts.filter(contact => {
        const name = (contact.displayName || '').toLowerCase();
        const qiaoId = (contact.contact_qiao_id || '').toLowerCase();
        return name.includes(keyword) || qiaoId.includes(keyword);
      });
    }

    // Group by first letter
    const groups = {};
    filteredContacts.forEach(contact => {
      const firstChar = this.getFirstLetter(contact.displayName);
      if (!groups[firstChar]) {
        groups[firstChar] = [];
      }
      groups[firstChar].push(contact);
    });

    // Convert to array and sort by letter
    const groupedArray = Object.keys(groups)
      .sort()
      .map(letter => ({
        letter: letter,
        contacts: groups[letter]
      }));

    return groupedArray;
  },

  getFirstLetter(name) {
    if (!name) return '#';

    const firstChar = name.charAt(0).toUpperCase();

    // Check if it's A-Z
    if (/[A-Z]/.test(firstChar)) {
      return firstChar;
    }

    // Check if it's Chinese character
    if (/[\u4e00-\u9fa5]/.test(firstChar)) {
      // Get pinyin first letter (simplified approach)
      const code = firstChar.charCodeAt(0);
      if (code >= 0x4e00 && code <= 0x9fa5) {
        // Use a simple mapping for common Chinese characters
        // For production, should use a proper pinyin library
        return this.getPinyinFirstLetter(firstChar);
      }
    }

    // For other characters, use #
    return '#';
  },

  getPinyinFirstLetter(char) {
    // Simplified pinyin mapping for common characters
    // For production, should use a proper pinyin library like pinyin-pro
    const code = char.charCodeAt(0);

    if (code >= 0x4e00 && code <= 0x9fa5) {
      // This is a very simplified approach
      // In production, use a proper pinyin library
      const pinyinMap = {
        '阿': 'A', '啊': 'A', '爱': 'A', '安': 'A',
        '八': 'B', '白': 'B', '百': 'B', '北': 'B',
        '才': 'C', '菜': 'C', '草': 'C', '曾': 'C',
        '大': 'D', '代': 'D', '丹': 'D', '当': 'D',
        // ... more mappings needed for production
      };

      return pinyinMap[char] || '#';
    }

    return '#';
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
  },

  onSearchInput(e) {
    this.setData({ searchKeyword: e.detail.value });
    // Re-group contacts with new search keyword
    this.updateContactsList(this.data.contacts);
  },

  goToContactInfo(e) {
    const convId = e.currentTarget.dataset.id;
    wx.navigateTo({
      url: `/pages/contact-info/contact-info?id=${convId}`
    });
  }
});

