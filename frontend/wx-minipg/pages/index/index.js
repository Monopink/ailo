import { getAvatarUrl } from '../../utils/avatar';
import { APP_CONFIG } from '../../utils/config';
import logger from '../../utils/logger';
import { getContacts } from '../../utils/storage';
import { requireAuthForPage } from '../../utils/auth-guard';

Page({
  data: {
    showSearch: false,
    chatList: [],
    unreadTotal: 0,
    loading: false,
    currentMenuIndex: -1
  },

  onLoad() {
    logger.info('Chat list page loaded');
    // Enforce auth; redirect to welcome if not logged in
    if (!requireAuthForPage(this)) {
      return;
    }
    this.updateNavigationTitle();
    this.loadChatList();
  },

  onShow() {
    // Enforce auth when page shows
    if (!requireAuthForPage(this)) {
      return;
    }
    // Reload chat list when page shows
    this.updateNavigationTitle();
    this.loadChatList();
  },

  updateNavigationTitle() {
    const brandName = APP_CONFIG.brandName || '敲敲';
    const unreadTotal = this.data.unreadTotal || 0;
    const title = unreadTotal > 0
      ? `${brandName}(${unreadTotal > 99 ? '99+' : unreadTotal})`
      : brandName;

    wx.setNavigationBarTitle({ title });
  },

  async loadChatList() {
    try {
      this.setData({
        loading: true
      });

      // Load from local storage
      const contacts = await getContacts();

      if (contacts.length > 0) {
        this.updateChatList(contacts);
      } else {
        // No contacts in storage
        this.setData({
          chatList: [],
          unreadTotal: 0,
          loading: false
        });
        this.updateNavigationTitle();
      }

    } catch (error) {
      logger.error('Failed to load chat list', {
        error: error.message || String(error)
      });
      this.setData({
        loading: false
      });

      wx.showToast({
        title: '加载失败',
        icon: 'none'
      });
    }
  },

  updateChatList(contacts) {
    const chatList = contacts.map(contact => ({
      ...contact,
      // Use avatar_alias_url if set, otherwise use profile avatar_url
      avatarUrl: getAvatarUrl(contact.avatar_alias_url || contact.avatar_url),
      // Use alias if set, otherwise use profile nickname
      displayName: contact.alias || contact.nickname || contact.contact_qiao_id
    }));

    // Calculate unread total
    const unreadTotal = chatList.reduce((sum, chat) => sum + (chat.unreadCount || 0), 0);

    this.setData({
      chatList,
      unreadTotal,
      loading: false
    });

    // Update navigation title
    this.updateNavigationTitle();
  },

  onScroll(e) {
    // Show search bar on scroll down
    if (e.detail.scrollTop < -50) {
      this.setData({ showSearch: true });
    } else if (e.detail.scrollTop > 0) {
      this.setData({ showSearch: false });
    }
  },

  goToSearch() {
    wx.navigateTo({ url: '/pages/search/search' });
  },

  goToChat(e) {
    const index = e.currentTarget.dataset.index;
    const item = this.data.chatList[index];

    // Don't navigate if swiping
    if (item && item.swiping) {
      return;
    }

    const convId = e.currentTarget.dataset.id;
    wx.navigateTo({
      url: `/pages/chat/chat?id=${convId}`
    });
  },

  // Menu handlers
  showMenu(e) {
    const index = e.currentTarget.dataset.index;
    this.setData({ currentMenuIndex: index });
  },

  hideMenu() {
    this.setData({ currentMenuIndex: -1 });
  },

  stopPropagation() {
    // Prevent menu close when clicking inside menu
  },

  goToContactInfo(e) {
    const convId = e.currentTarget.dataset.id;
    const index = e.currentTarget.dataset.index;

    // Close menu
    const chatList = this.data.chatList;
    chatList[index].showMenu = false;
    this.setData({ chatList });

    // Navigate to contact info page
    wx.navigateTo({
      url: `/pages/contact-info/contact-info?id=${convId}`
    });
  },

  // Mark as unread
  markAsUnread(e) {
    const index = e.currentTarget.dataset.index;
    const chatList = this.data.chatList;

    // Add unread count (local operation only)
    chatList[index].unreadCount = (chatList[index].unreadCount || 0) + 1;

    // Close menu
    chatList[index].showMenu = false;

    this.setData({ chatList });

    wx.showToast({
      title: '已标为未读',
      icon: 'success'
    });
  },

  // Delete chat
  deleteChat(e) {
    const index = e.currentTarget.dataset.index;
    const chatList = this.data.chatList;

    // Close menu
    chatList[index].showMenu = false;
    this.setData({ chatList });

    // Show confirmation dialog
    wx.showModal({
      title: '确认删除',
      content: '删除后聊天记录将被清空',
      success: (res) => {
        if (res.confirm) {
          // Remove from list
          chatList.splice(index, 1);
          this.setData({ chatList });

          wx.showToast({
            title: '已删除',
            icon: 'success'
          });

          logger.info('Chat deleted', { index });
        }
      }
    });
  }
});
