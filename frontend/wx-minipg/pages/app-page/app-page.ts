import { createPageLayoutData, type PageLayoutData } from '../../templates/page-layout';
import { getLogger } from '../../utils/logger';
import { type ScreenModel } from '../../services/pages/page-state';
import { createAppPageService } from '../../services/pages/app-page-service';

const logger = getLogger('AppPage');

interface AppPageData extends Record<string, unknown> {
  pageLayoutData: PageLayoutData;
  pageKey: string;
  title: string;
  contentRendered: string;
}

interface AppPageCustom {
  appPageService: ReturnType<typeof createAppPageService>;
  applyScreenModel(screenModel: ScreenModel): void;
  loadAppPage(): Promise<void>;
}

const buildPageLayoutScreenModelPayload = (screenModel: ScreenModel): Record<string, unknown> => ({
  'pageLayoutData.screenModel': screenModel,
});

Page<AppPageData, AppPageCustom>({
  data: {
    pageLayoutData: createPageLayoutData({
      screenModel: {
        screenState: 'booting',
        contentVariant: 'blank',
        refreshState: 'idle',
      },
      hasFooter: false,
      emptyMessage: '',
    }),
    pageKey: '',
    title: '',
    contentRendered: '',
  },

  appPageService: null as unknown as ReturnType<typeof createAppPageService>,

  applyScreenModel(screenModel: ScreenModel) {
    this.setData(buildPageLayoutScreenModelPayload(screenModel));
  },

  async onLoad(options: Record<string, string | undefined>) {
    this.appPageService = createAppPageService();
    const bootstrap = this.appPageService.bootstrap(options.pageKey);
    this.setData({
      pageKey: bootstrap.pageKey,
      ...buildPageLayoutScreenModelPayload(bootstrap.screenModel),
    });
    if (bootstrap.pageKey.length === 0) {
      return;
    }
    await this.loadAppPage();
  },

  onUnload() {
    this.appPageService.dispose();
  },

  async loadAppPage() {
    if (this.data.pageKey.length === 0) {
      this.applyScreenModel({
        screenState: 'ready',
        contentVariant: 'blank',
        refreshState: 'idle',
      });
      return;
    }

    this.applyScreenModel({
      screenState: 'booting',
      contentVariant: 'blank',
      refreshState: 'idle',
    });

    const result = await this.appPageService.load(this.data.pageKey);
    if (result === null) {
      return;
    }
    this.setData({
      title: result.title,
      contentRendered: result.contentRendered,
      ...buildPageLayoutScreenModelPayload(result.screenModel),
    });
    if (result.screenModel.contentVariant === 'blank') {
      logger.error('Load app page failed', { pageKey: this.data.pageKey });
    }
  },
});
