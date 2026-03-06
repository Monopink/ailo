import { createPageLayoutData, type PageLayoutData } from '../../templates/page-layout';
import { getLogger } from '../../utils/logger';
import { isNonEmptyString } from '../../utils/guards';

const logger = getLogger('Boot');

interface BootPageData {
  pageLayoutData: PageLayoutData;
  routed: boolean;
}

interface BootPageCustom {
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
  },

  onLoad(options: RouteOptions) {
    if (this.data.routed) {
      return;
    }

    try {
      const token = wx.getStorageSync<string | null>('auth_token');
      const hasToken = isNonEmptyString(token);

      logger.info('Boot routing', {
        hasToken,
        options,
      });

      if (hasToken) {
        this._routeOnce(() => {
          void wx.switchTab({ url: '/pages/index/index' });
        });
        return;
      }

      // Always show login page when not logged in
      this._routeOnce(() => {
        void wx.redirectTo({ url: '/pages/login/login' });
      });
    } catch (error) {
      const err = toError(error);
      logger.error('Boot routing error', { error: err.message });
      this._routeOnce(() => {
        void wx.redirectTo({ url: '/pages/login/login' });
      });
    }
  },

  _routeOnce(callback: () => void) {
    if (this.data.routed) {
      return;
    }

    this.setData({ routed: true });

    if (typeof wx.nextTick === 'function') {
      wx.nextTick(callback);
      return;
    }

    setTimeout(callback, 0);
  },
});
