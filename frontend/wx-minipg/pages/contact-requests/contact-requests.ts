import { createPageLayoutData, type PageLayoutData } from '../../templates/page-layout';

interface ContactRequest {
  id: string;
  nickname: string;
  avatar: string;
  message: string;
  gender?: number | null;
}

interface ContactRequestsPageData {
  pageLayoutData: PageLayoutData;
  requests: ContactRequest[];
}

interface ContactRequestsPageCustom {
  loadRequests(): void;
  handleApprove(event: WechatMiniprogram.TouchEvent): void;
  handleReject(event: WechatMiniprogram.TouchEvent): void;
  onRetry(): void;
}

Page<ContactRequestsPageData, ContactRequestsPageCustom>({
  data: {
    pageLayoutData: createPageLayoutData({
      isEmpty: true,
      emptyMessage: '暂无新的联系人申请',
    }),
    requests: [],
  },

  onLoad() {
    this.loadRequests();
  },

  loadRequests() {
    // API 尚未接入，保持空列表并展示统一空状态。
    this.setData({
      'pageLayoutData.isLoading': false,
      'pageLayoutData.isEmpty': this.data.requests.length === 0,
    });
  },

  handleApprove(event) {
    const { id } = event.currentTarget.dataset as { id: string };
    void id; // TODO: Will be used for API call - POST /contacts/requests/${id}/accept
    void wx.showToast({
      title: '已通过好友请求',
      icon: 'success',
    });
  },

  handleReject(event) {
    const { id } = event.currentTarget.dataset as { id: string };
    void id; // TODO: Will be used for API call - POST /contacts/requests/${id}/reject
    void wx.showToast({
      title: '已拒绝该请求',
      icon: 'none',
    });
  },

  onRetry() {
    this.loadRequests();
  },
});
