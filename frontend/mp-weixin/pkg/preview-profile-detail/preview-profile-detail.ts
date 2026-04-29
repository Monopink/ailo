import { createPageLayoutData, type PageLayoutData } from '../../templates/page-layout';
import { previewMockData, type PreviewGuestProfile } from '../preview-common/data';
import { ensurePreviewAccess } from '../../utils/runtime-segment';

interface PreviewProfileDetailPageData {
  pageLayoutData: PageLayoutData;
  guestProfile: PreviewGuestProfile;
}

interface PreviewProfileDetailPageCustom {
  handleReadonlyAction(): void;
}

Page<PreviewProfileDetailPageData, PreviewProfileDetailPageCustom>({
  data: {
    pageLayoutData: createPageLayoutData({
      screenModel: {
        screenState: 'ready',
        contentVariant: 'data',
        refreshState: 'idle',
      },
      hasFooter: false,
      emptyMessage: '暂无内容',
    }),
    guestProfile: previewMockData.getGuestProfile(),
  },

  onLoad() {
    if (!ensurePreviewAccess('/pkg/preview-profile-detail/preview-profile-detail')) {
      return;
    }
  },

  onShow() {
    if (!ensurePreviewAccess('/pkg/preview-profile-detail/preview-profile-detail')) {
      return;
    }
    this.setData({
      guestProfile: previewMockData.getGuestProfile(),
    });
  },

  handleReadonlyAction() {
    void wx.showToast({ title: '游客数据不可修改', icon: 'none' });
  },
});
