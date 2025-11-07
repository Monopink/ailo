import { requireAuth } from '../../utils/auth-guard';
import { getAvatarUrl } from '../../utils/avatar';
import { APP_CONFIG } from '../../utils/config';
import logger from '../../utils/logger';
import { clearMessages, getContacts, saveContacts } from '../../utils/storage';
import { del } from '../../utils/api';
import { formatMessageTime } from '../../utils/format';

Page({
  data: {
    contactList: [],
    unreadTotal: 0,
    loading: false,
    currentMenuIndex: -1,
    isEmpty: false
  },

  async onLoad() {
    logger.info('Contact list page loaded');
    const isAuth = await requireAuth(this);
    if (!isAuth) return;
    this.updateNavigationTitle();
    this.loadContactList();
  },

  async onShow() {
    const isAuth = await requireAuth(this);
    if (!isAuth) return;
    this.updateNavigationTitle();
    this.loadContactList();
  },

  updateNavigationTitle() {
    const brandName = APP_CONFIG.brandName || '';
    const unreadTotal = this.data.unreadTotal || 0;
    const title = unreadTotal > 0
      ? `${brandName}(${unreadTotal > 99 ? '99+' : unreadTotal})`
      : (brandName || '');
    if (title) wx.setNavigationBarTitle({ title });
  },

  async loadContactList() {
    try {
      this.setData({ loading: true });
      const contacts = await getContacts();
      this.updateContactList(contacts || []);
    } catch (error) {
      logger.error('Failed to load contact list', { error: error.message || String(error) });
      this.setData({ loading: false, isEmpty: true });
      wx.showToast({ title: '加载失败', icon: 'none' });
    }
  },

  updateContactList(contacts) {
    const contactList = (contacts || []).map(contact => {
      const unreadCount = contact.unreadCount || 0;
      return {
        ...contact,
        avatarUrl: getAvatarUrl(contact.custom_avatar_url || contact.avatar_url),
        displayName: contact.alias || contact.nickname || contact.contact_qiao_id,
        lastMessageTime: formatMessageTime(contact.last_message_time),
        lastMessage: contact.last_message_content || '',
        hasUnread: unreadCount > 0,
        unreadBadge: unreadCount > 99 ? '99+' : String(unreadCount)
      };
    });

    const unreadTotal = contactList.reduce((sum, contact) => sum + (contact.unreadCount || 0), 0);
    const loading = false;
    const isEmpty = contactList.length === 0 && !loading;

    this.setData({ contactList, unreadTotal, loading, isEmpty });
    this.updateNavigationTitle();
  },

  goToChat(e) {
    const convId = e.currentTarget.dataset.id;
    if (!convId) return;
    wx.navigateTo({ url: `/pages/chat/chat?id=${convId}` });
  },

  // Menu handlers
  showMenu(e) {
    const index = e.currentTarget.dataset.index;
    this.setData({ currentMenuIndex: index });
  },

  hideMenu() {
    this.setData({ currentMenuIndex: -1 });
  },

  stopPropagation() {},

  goToContactInfo(e) {
    const convId = e.currentTarget.dataset.id;
    this.setData({ currentMenuIndex: -1 });
    wx.navigateTo({ url: `/pages/contact-info/contact-info?id=${convId}` });
  },

  markAsUnread(e) {
    const index = e.currentTarget.dataset.index;
    const contactList = this.data.contactList.slice();
    if (contactList[index]) {
      const current = contactList[index];
      const count = (current.unreadCount || 0) + 1;
      current.unreadCount = count;
      current.hasUnread = true;
      current.unreadBadge = count > 99 ? '99+' : String(count);
      this.setData({ contactList, currentMenuIndex: -1 });
      wx.showToast({ title: '已标为未读', icon: 'success' });
      const unreadTotal = contactList.reduce((sum, contact) => sum + (contact.unreadCount || 0), 0);
      this.setData({ unreadTotal });
      this.updateNavigationTitle();
    }
  },

  deleteContact(e) {
    const index = e.currentTarget.dataset.index;
    const convId = e.currentTarget.dataset.id;
    this.setData({ currentMenuIndex: -1 });

    if (index === undefined || !convId) {
      return;
    }

    wx.showModal({
      title: '删除联系人',
      content: '删除后将解除联系并清空本地聊天记录，确定继续？',
      confirmColor: '#ff4d4f',
      success: async (res) => {
        if (!res.confirm) return;

        wx.showLoading({ title: '处理中', mask: true });
        try {
          await del(`/contacts/${convId}`);

          const currentContacts = await getContacts();
          const updatedContacts = (currentContacts || []).filter(contact => contact.conv_id !== convId);
          await saveContacts(updatedContacts);
          await clearMessages(convId);

          this.updateContactList(updatedContacts);

          wx.showToast({ title: '已删除', icon: 'success' });
          logger.info('Contact deleted', { convId });
        } catch (error) {
          logger.error('Delete contact failed', { convId, error: error.message || String(error) });
          wx.showToast({ title: error.message || '删除失败，请稍后重试', icon: 'none' });
        } finally {
          wx.hideLoading();
        }
      }
    });
  }
});
