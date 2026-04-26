import { createPageLayoutData, type PageLayoutData } from '../../templates/page-layout';
import { getLogger } from '../../utils/logger';
import authService from '../../utils/auth-service';

const logger = getLogger('Boot');
const LOADING_INDICATOR_DELAY_MS = 220;
const LOADING_TEXT_DELAY_MS = 1200;

type TimerHandle = ReturnType<typeof setTimeout>;

interface BootPageData {
  pageLayoutData: PageLayoutData;
  routed: boolean;
  showLoadingIndicator: boolean;
  showLoadingText: boolean;
}

interface BootPageCustom {
  _loadingIndicatorTimer: TimerHandle | null;
  _loadingTextTimer: TimerHandle | null;
  _startLoadingFeedback(): void;
  _clearLoadingFeedback(): void;
  _routeOnce(callback: () => void): void;
}

const toError = (error: unknown): Error => {
  if (error instanceof Error) {
    return error;
  }
  if (typeof error === 'string') {
    return new Error(error);
  }
  try {
    return new Error(JSON.stringify(error));
  } catch {
    return new Error('Unknown error');
  }
};

type RouteOptions = Record<string, string | undefined>;

const normalizeQueryValue = (value: string | undefined): string | null => {
  if (typeof value !== 'string') {
    return null;
  }
  const trimmed = value.trim();
  return trimmed === '' ? null : trimmed;
};

const buildRouteUrl = (basePath: string, options: RouteOptions): string => {
  const params: string[] = [];

  const inviteCode = normalizeQueryValue(options.inviteCode);
  if (inviteCode !== null) {
    params.push(`inviteCode=${encodeURIComponent(inviteCode)}`);
  }

  const campaignCode = normalizeQueryValue(options.campaignCode);
  if (campaignCode !== null) {
    params.push(`campaignCode=${encodeURIComponent(campaignCode)}`);
  }

  if (params.length === 0) {
    return basePath;
  }
  return `${basePath}?${params.join('&')}`;
};

Page<BootPageData, BootPageCustom>({
  data: {
    pageLayoutData: createPageLayoutData({
      screenModel: {
        screenState: 'ready',
        contentVariant: 'data',
        refreshState: 'idle',
      },
      hasFooter: false,
      emptyMessage: '',
    }),
    routed: false,
    showLoadingIndicator: false,
    showLoadingText: false,
  },
  _loadingIndicatorTimer: null,
  _loadingTextTimer: null,

  async onLoad(options: RouteOptions) {
    if (this.data.routed) {
      return;
    }
    this._startLoadingFeedback();

    try {
      const app = getApp<AppInstance>();
      const isAuthenticated = await authService.initialize();

      logger.info('Boot routing', {
        isAuthenticated,
        needsProfileSetup: authService.needsProfileSetup(),
        options,
      });

      if (!isAuthenticated) {
        const loginUrl = buildRouteUrl('/pages/login/login', options);
        this._routeOnce(() => {
          void wx.redirectTo({ url: loginUrl });
        });
        return;
      }

      try {
        await app.getConversationStore().init();
        await app.initMessageService();
      } catch (error) {
        const err = toError(error);
        logger.warn('Boot warmup failed, continue routing', { error: err.message });
      }

      if (authService.needsProfileSetup()) {
        const setupUrl = buildRouteUrl('/pages/setup/setup', options);
        this._routeOnce(() => {
          void wx.redirectTo({ url: setupUrl });
        });
        return;
      }

      this._routeOnce(() => {
        void wx.switchTab({ url: '/pages/index/index' });
      });
    } catch (error) {
      const err = toError(error);
      logger.error('Boot routing error', { error: err.message });
      this._routeOnce(() => {
        void wx.redirectTo({ url: '/pages/login/login' });
      });
    }
  },

  onUnload() {
    this._clearLoadingFeedback();
  },

  _startLoadingFeedback() {
    this._clearLoadingFeedback();

    this._loadingIndicatorTimer = setTimeout(() => {
      if (this.data.routed) {
        return;
      }
      this.setData({ showLoadingIndicator: true });
    }, LOADING_INDICATOR_DELAY_MS);

    this._loadingTextTimer = setTimeout(() => {
      if (this.data.routed) {
        return;
      }
      this.setData({
        showLoadingIndicator: true,
        showLoadingText: true,
      });
    }, LOADING_TEXT_DELAY_MS);
  },

  _clearLoadingFeedback() {
    if (this._loadingIndicatorTimer !== null) {
      clearTimeout(this._loadingIndicatorTimer);
      this._loadingIndicatorTimer = null;
    }
    if (this._loadingTextTimer !== null) {
      clearTimeout(this._loadingTextTimer);
      this._loadingTextTimer = null;
    }
  },

  _routeOnce(callback: () => void) {
    if (this.data.routed) {
      return;
    }

    this._clearLoadingFeedback();
    this.setData({ routed: true });

    if (typeof wx.nextTick === 'function') {
      wx.nextTick(callback);
      return;
    }

    setTimeout(callback, 0);
  },
});
