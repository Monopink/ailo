import { get, del } from '../../utils/api';
import { getAvatarUrl } from '../../utils/avatar';
import logger from '../../utils/logger';
import {
  clearMessages,
  getContactByConvId,
  getContacts,
  saveContacts
} from '../../utils/storage';

Page({
  data: {
    convId: '',
    contact: null,
    loading: true,
    isPinned: false,
    isMuted: false
  },

  async onLoad(options) {
    const convId = options.id;

    if (!convId) {
      wx.showToast({
        title: '参数错误',
        icon: 'none'
      });
      wx.navigateBack();
      return;
    }

    this.setData({ convId });

    // Load contact info from local storage first
    const cachedContact = await getContactByConvId(convId);
    if (cachedContact) {
      this.setData({
        contact: {
          ...cachedContact,
          avatar_url: getAvatarUrl(cachedContact.avatar_url),
          custom_avatar_url: cachedContact.custom_avatar_url ? getAvatarUrl(cachedContact.custom_avatar_url) : null
        },
        isPinned: cachedContact.is_pinned || false,
        isMuted: cachedContact.is_muted || false,
        loading: false
      });
    }

    // Refresh contact info from API
    await this.refreshContactInfo();
  },

  async refreshContactInfo() {
    try {
      // Fetch latest contact info
      const result = await get(`/contacts/${this.data.convId}/conversation`);

      // Update contact in local storage
      const contacts = await getContacts();
      const index = contacts.findIndex(c => c.conv_id === this.data.convId);

      if (index !== -1) {
        // Update existing contact
        contacts[index] = {
          ...contacts[index],
          alias: result.alias,
          custom_avatar_url: result.custom_avatar_url,
          remark: result.remark,
          nickname: result.contact_info?.nickname,
          avatar_url: result.contact_info?.avatar_url,
          gender: result.contact_info?.gender
        };

        await saveContacts(contacts);

        this.setData({
          contact: {
            ...contacts[index],
            avatar_url: getAvatarUrl(contacts[index].avatar_url),
            custom_avatar_url: contacts[index].custom_avatar_url ? getAvatarUrl(contacts[index].custom_avatar_url) : null
          },
          loading: false
        });

        logger.info('Contact info refreshed', { conv_id: this.data.convId });
      }
    } catch (error) {
      logger.error('Failed to refresh contact info', { error });
      this.setData({ loading: false });
    }
  },

  goToChat() {
    wx.navigateTo({
      url: `/pages/chat/chat?id=${this.data.convId}`
    });
  },

  editRemarkAndTags() {
    // TODO: Implement remark and tags edit page
    wx.showToast({
      title: '功能开发中',
      icon: 'none'
    });
  },

  onPinnedChange(e) {
    const isPinned = e.detail.value;
    this.setData({ isPinned });

    // TODO: Call API to update pinned status
    logger.info('Pinned status changed', { conv_id: this.data.convId, is_pinned: isPinned });

    wx.showToast({
      title: isPinned ? '已置顶' : '已取消置顶',
      icon: 'success'
    });
  },

  onMutedChange(e) {
    const isMuted = e.detail.value;
    this.setData({ isMuted });

    // TODO: Call API to update muted status
    logger.info('Muted status changed', { conv_id: this.data.convId, is_muted: isMuted });

    wx.showToast({
      title: isMuted ? '已开启免打扰' : '已关闭免打扰',
      icon: 'success'
    });
  },

  clearChatHistory() {
    wx.showModal({
      title: '提示',
      content: '确定清空聊天记录吗？',
      success: async (res) => {
        if (res.confirm) {
          try {
            await clearMessages(this.data.convId);

            wx.showToast({
              title: '已清空',
              icon: 'success'
            });

            logger.info('Chat history cleared', { conv_id: this.data.convId });
          } catch (error) {
            logger.error('Failed to clear chat history', { error });

            wx.showToast({
              title: '清空失败',
              icon: 'none'
            });
          }
        }
      }
    });
  },

  deleteContact() {
    wx.showModal({
      title: '提示',
      content: '确定删除该联系人吗？删除后将从联系人列表移除。',
      confirmColor: '#ff4d4f',
      success: async (res) => {
        if (!res.confirm) return;

        wx.showLoading({ title: '正在删除', mask: true });
        try {
          await del(`/contacts/${this.data.convId}`);

          const contacts = await getContacts();
          const updatedContacts = (contacts || []).filter(contact => contact.conv_id !== this.data.convId);
          await saveContacts(updatedContacts);
          await clearMessages(this.data.convId);

          wx.showToast({
            title: '已删除',
            icon: 'success'
          });

          logger.info('Contact deleted', { conv_id: this.data.convId });

          setTimeout(() => {
            wx.navigateBack();
          }, 300);
        } catch (error) {
          logger.error('Failed to delete contact', { error: error.message || String(error) });

          wx.showToast({
            title: error.message || '删除失败，请稍后重试',
            icon: 'none'
          });
        } finally {
          wx.hideLoading();
        }
      }
    });
  }
});
