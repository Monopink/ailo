import { createPageLayoutData, type PageLayoutData } from '../../templates/page-layout';
import {
  createContactRequestsPageService,
  type ContactRequestItem,
} from '../services/pages/contact-requests-service';

interface ContactRequestsPageData {
  pageLayoutData: PageLayoutData;
  requests: ContactRequestItem[];
}

interface ContactRequestsPageCustom {
  contactRequestsPageService: ReturnType<typeof createContactRequestsPageService>;
  onUnload(): void;
  loadRequests(): void;
  handleApprove(event: WechatMiniprogram.TouchEvent): void;
  handleReject(event: WechatMiniprogram.TouchEvent): void;
}

Page<ContactRequestsPageData, ContactRequestsPageCustom>({
  data: {
    pageLayoutData: createPageLayoutData({
      screenModel: {
        screenState: 'ready',
        contentVariant: 'empty',
        refreshState: 'idle',
      },
      emptyMessage: '暂无新的联系人申请',
    }),
    requests: [],
  },

  contactRequestsPageService: null as unknown as ReturnType<
    typeof createContactRequestsPageService
  >,

  onLoad() {
    this.contactRequestsPageService = createContactRequestsPageService();
    this.loadRequests();
  },

  onUnload() {
    this.contactRequestsPageService.dispose();
  },

  loadRequests() {
    const result = this.contactRequestsPageService.load(this.data.requests);
    if (result === null) {
      return;
    }
    this.setData({
      requests: result.requests,
      'pageLayoutData.screenModel': result.screenModel,
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
});
