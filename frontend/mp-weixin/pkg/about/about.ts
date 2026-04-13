import { createPageLayoutData, type PageLayoutData } from '../../templates/page-layout';
import { getLogger } from '../../utils/logger';

const logger = getLogger('About');
const USER_AGREEMENT_PAGE_KEY = 'user_agreement';
const PRIVACY_POLICY_PAGE_KEY = 'privacy_policy';
const CONTACT_US_PAGE_KEY = 'contact_us';

interface AboutPageData extends Record<string, unknown> {
  pageLayoutData: PageLayoutData;
}

interface AboutPageCustom {
  navigateToUserAgreement(): void;
  navigateToPrivacyPolicy(): void;
  navigateToContactUs(): void;
}

Page<AboutPageData, AboutPageCustom>({
  data: {
    pageLayoutData: createPageLayoutData({
      screenModel: {
        screenState: 'ready',
        contentVariant: 'data',
        refreshState: 'idle',
      },
      hasFooter: false,
    }),
  },

  onLoad() {
    logger.info('About page loaded');
  },

  navigateToUserAgreement() {
    void wx.navigateTo({
      url: `/pkg/app-page/app-page?pageKey=${USER_AGREEMENT_PAGE_KEY}`,
    });
  },

  navigateToPrivacyPolicy() {
    void wx.navigateTo({
      url: `/pkg/app-page/app-page?pageKey=${PRIVACY_POLICY_PAGE_KEY}`,
    });
  },

  navigateToContactUs() {
    void wx.navigateTo({
      url: `/pkg/app-page/app-page?pageKey=${CONTACT_US_PAGE_KEY}`,
    });
  },
});
