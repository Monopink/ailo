import { createPageLayoutData, type PageLayoutData } from '../../templates/page-layout';
import { getLogger } from '../../utils/logger';

const logger = getLogger('About');

interface AboutPageData extends Record<string, unknown> {
  pageLayoutData: PageLayoutData;
  version: string;
}

interface AboutPageCustom {
  navigateToUserAgreement(): void;
  navigateToPrivacyPolicy(): void;
  onRetry(): void;
}

Page<AboutPageData, AboutPageCustom>({
  data: {
    pageLayoutData: createPageLayoutData({
      isLoading: false,
      hasFooter: false,
    }),
    version: '1.0.0',
  },

  onLoad() {
    logger.info('About page loaded');
  },

  navigateToUserAgreement() {
    // TODO: Navigate to user agreement page
    void wx.showToast({
      title: '功能开发中',
      icon: 'none',
    });
  },

  navigateToPrivacyPolicy() {
    // TODO: Navigate to privacy policy page
    void wx.showToast({
      title: '功能开发中',
      icon: 'none',
    });
  },

  onRetry() {
    // No retry needed for about page
  },
});
