import { getLogger } from '../../utils/logger';

const logger = getLogger('Boot');

Page({
  data: {
    routed: false
  },

  onLoad(options) {
    // Avoid double routing
    if (this.data.routed) return;

    try {
      const token = wx.getStorageSync('auth_token');
      const hasSeenWelcome = !!wx.getStorageSync('hasSeenWelcome');

      logger.info('Boot routing', { hasToken: !!token, hasSeenWelcome, options });

      // If has token, go to chat tab directly
      if (token) {
        this._routeOnce(() => wx.switchTab({ url: '/pages/index/index' }));
        return;
      }

      // No token: if user hasn't seen welcome, go to welcome; else go to login
      if (!hasSeenWelcome) {
        this._routeOnce(() => wx.redirectTo({ url: '/pages/welcome/welcome' }));
      } else {
        this._routeOnce(() => wx.redirectTo({ url: '/pages/login/login' }));
      }
    } catch (e) {
      // Fallback to welcome on any error
      logger.error('Boot routing error', { error: e.message || String(e) });
      this._routeOnce(() => wx.redirectTo({ url: '/pages/welcome/welcome' }));
    }
  },

  _routeOnce(fn) {
    if (this.data.routed) return;
    this.setData({ routed: true });
    // Use nextTick to ensure the boot page has mounted
    if (typeof wx.nextTick === 'function') {
      wx.nextTick(fn);
    } else {
      setTimeout(fn, 0);
    }
  }
});

