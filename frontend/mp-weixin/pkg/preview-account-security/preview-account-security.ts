import { createPageLayoutData, type PageLayoutData } from '../../templates/page-layout';
import { ensurePreviewAccess } from '../../utils/runtime-segment';

interface PreviewAccountSecurityPageData {
  pageLayoutData: PageLayoutData;
  phoneMasked: string;
}

interface PreviewAccountSecurityPageCustom {
  handleReadonlyAction(): void;
}

Page<PreviewAccountSecurityPageData, PreviewAccountSecurityPageCustom>({
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
    phoneMasked: '未绑定',
  },

  onLoad() {
    if (!ensurePreviewAccess('/pkg/preview-account-security/preview-account-security')) {
      return;
    }
  },

  onShow() {
    if (!ensurePreviewAccess('/pkg/preview-account-security/preview-account-security')) {
      return;
    }
  },

  handleReadonlyAction() {
    void wx.showToast({ title: '游客数据不可修改', icon: 'none' });
  },
});
