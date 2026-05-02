import { createPageLayoutData, type PageLayoutData } from '../../templates/page-layout';
import authService from '../../utils/auth-service';
import { getLogger } from '../../utils/logger';
import { shouldAllowPreviewAccess } from '../../utils/runtime-segment';

const logger = getLogger('About');
const USER_AGREEMENT_PAGE_KEY = 'user_agreement';
const PRIVACY_POLICY_PAGE_KEY = 'privacy_policy';
const CONTACT_US_PAGE_KEY = 'contact_us';

interface AboutPageData extends Record<string, unknown> {
  pageLayoutData: PageLayoutData;
  previewFallbackEnabled: boolean;
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
    previewFallbackEnabled: false,
  },

  onLoad(options: Record<string, string | undefined>) {
    const previewFlag = options.previewMode === '1';
    const previewFallbackEnabled =
      previewFlag && shouldAllowPreviewAccess() && !authService.isAuthenticated();
    this.setData({ previewFallbackEnabled });
    logger.info('About page loaded');
  },

  navigateToUserAgreement() {
    const previewFallbackQuery = this.data.previewFallbackEnabled ? '&previewFallback=1' : '';
    void wx.navigateTo({
      url: `/pkg/app-page/app-page?pageKey=${USER_AGREEMENT_PAGE_KEY}${previewFallbackQuery}`,
    });
  },

  navigateToPrivacyPolicy() {
    const previewFallbackQuery = this.data.previewFallbackEnabled ? '&previewFallback=1' : '';
    void wx.navigateTo({
      url: `/pkg/app-page/app-page?pageKey=${PRIVACY_POLICY_PAGE_KEY}${previewFallbackQuery}`,
    });
  },

  navigateToContactUs() {
    void wx.navigateTo({
      url: `/pkg/app-page/app-page?pageKey=${CONTACT_US_PAGE_KEY}`,
    });
  },
});
