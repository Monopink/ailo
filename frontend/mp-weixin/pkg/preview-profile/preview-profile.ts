import { createPageLayoutData, type PageLayoutData } from '../../templates/page-layout';
import { previewMockData, type PreviewGuestProfile } from '../preview-common/data';
import {
  getPreviewTabPath,
  listPreviewTabItems,
  type PreviewTabItem,
  type PreviewTabKey,
} from '../preview-common/navigation';
import { ensurePreviewAccess } from '../../utils/runtime-segment';

interface PreviewProfilePageData {
  pageLayoutData: PageLayoutData;
  guestProfile: PreviewGuestProfile;
  tabItems: PreviewTabItem[];
  activeTabKey: PreviewTabKey;
  showBuildInfo: boolean;
  buildInfoText: string;
}

interface PreviewProfilePageCustom {
  navigateToProfileDetail(): void;
  navigateToAccountSecurity(): void;
  navigateToAbout(): void;
  handleTabTap(event: WechatMiniprogram.BaseEvent): void;
}

const getDatasetValue = (event: WechatMiniprogram.BaseEvent, key: string): unknown => {
  const dataset = event.currentTarget.dataset as Record<string, unknown> | undefined;
  return dataset?.[key];
};

Page<PreviewProfilePageData, PreviewProfilePageCustom>({
  data: {
    pageLayoutData: createPageLayoutData({
      screenModel: {
        screenState: 'ready',
        contentVariant: 'data',
        refreshState: 'idle',
      },
      hasFooter: true,
      emptyMessage: '暂无内容',
    }),
    guestProfile: previewMockData.getGuestProfile(),
    tabItems: listPreviewTabItems(),
    activeTabKey: 'profile',
    showBuildInfo: false,
    buildInfoText: '',
  },

  onLoad() {
    if (!ensurePreviewAccess('/pkg/preview-profile/preview-profile')) {
      return;
    }
  },

  onShow() {
    if (!ensurePreviewAccess('/pkg/preview-profile/preview-profile')) {
      return;
    }
    this.setData({
      guestProfile: previewMockData.getGuestProfile(),
      tabItems: listPreviewTabItems(),
      activeTabKey: 'profile',
    });
  },

  navigateToProfileDetail() {
    void wx.navigateTo({ url: '/pkg/preview-profile-detail/preview-profile-detail' });
  },

  navigateToAccountSecurity() {
    void wx.navigateTo({ url: '/pkg/preview-account-security/preview-account-security' });
  },

  navigateToAbout() {
    void wx.navigateTo({ url: '/pkg/about/about?previewMode=1' });
  },

  handleTabTap(event: WechatMiniprogram.BaseEvent) {
    const tabKey = getDatasetValue(event, 'key');
    if (tabKey !== 'index' && tabKey !== 'square' && tabKey !== 'profile') {
      return;
    }
    if (tabKey === this.data.activeTabKey) {
      return;
    }
    void wx.redirectTo({ url: getPreviewTabPath(tabKey) });
  },
});
