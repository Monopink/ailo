import { fetchAppPage } from '../../utils/app-page-service';
import { isNonEmptyString } from '../../utils/guards';
import { BasePageService } from './base-page-service';
import { createBootingScreenModel, createReadyScreenModel, type ScreenModel } from './page-state';

export interface AppPageBootstrapResult {
  screenModel: ScreenModel;
  pageKey: string;
}

export interface AppPageLoadResult {
  screenModel: ScreenModel;
  title: string;
  contentRendered: string;
}

export class AppPageService extends BasePageService {
  bootstrap(rawPageKey: string | undefined): AppPageBootstrapResult {
    const pageKey = typeof rawPageKey === 'string' ? rawPageKey.trim() : '';
    if (!isNonEmptyString(pageKey)) {
      return {
        screenModel: createReadyScreenModel({ contentVariant: 'blank' }),
        pageKey: '',
      };
    }
    return {
      screenModel: createBootingScreenModel(),
      pageKey,
    };
  }

  async load(pageKey: string): Promise<AppPageLoadResult | null> {
    if (!isNonEmptyString(pageKey)) {
      return {
        screenModel: createReadyScreenModel({ contentVariant: 'blank' }),
        title: '',
        contentRendered: '',
      };
    }

    const seq = this.startRequest();
    try {
      const page = await fetchAppPage(pageKey);
      if (!this.isRequestActive(seq)) {
        return null;
      }
      const rendered = page.contentRendered.trim();
      return {
        screenModel: createReadyScreenModel({
          contentVariant: rendered.length === 0 ? 'blank' : 'data',
          refreshState: 'idle',
        }),
        title: page.title,
        contentRendered: rendered,
      };
    } catch {
      if (!this.isRequestActive(seq)) {
        return null;
      }
      return {
        screenModel: createReadyScreenModel({ contentVariant: 'blank' }),
        title: '',
        contentRendered: '',
      };
    }
  }
}

export const createAppPageService = (): AppPageService => new AppPageService();
