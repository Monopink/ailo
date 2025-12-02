import { getLogger } from '../../utils/logger';

const logger = getLogger('Boot');

interface BootPageData {
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
    routed: false,
  },

  onLoad(options: RouteOptions) {
    if (this.data.routed) {
      return;
    }

    try {
      const token = wx.getStorageSync<string | null>('auth_token');
      const hasSeenWelcome = Boolean(wx.getStorageSync<boolean>('hasSeenWelcome'));

      logger.info('Boot routing', {
        hasToken: Boolean(token),
        hasSeenWelcome,
        options,
      });

      if (token) {
        this._routeOnce(() => {
          void wx.switchTab({ url: '/pages/index/index' });
        });
        return;
      }

      if (!hasSeenWelcome) {
        this._routeOnce(() => {
          void wx.redirectTo({ url: '/pages/welcome/welcome' });
        });
      } else {
        this._routeOnce(() => {
          void wx.redirectTo({ url: '/pages/login/login' });
        });
      }
    } catch (error) {
      const err = toError(error);
      logger.error('Boot routing error', { error: err.message });
      this._routeOnce(() => {
        void wx.redirectTo({ url: '/pages/welcome/welcome' });
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
