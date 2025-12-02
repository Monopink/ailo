import { getLogger } from './logger';
import { get } from './api';

const logger = getLogger('CaptchaUtil');

export async function fetchCaptchaConfig() {
  try {
    const cfg = await get('/system/captcha-config', {}, { auth: false });
    return {
      provider: cfg.provider || 'none',
      sceneId: cfg.scene_id || '',
      region: cfg.region || 'cn',
      mode: cfg.mode || 'popup',
      language: cfg.language || 'cn'
    };
  } catch (e) {
    logger.error('fetchCaptchaConfig failed', { error: e.message || String(e) });
    return { provider: 'none', sceneId: '', region: 'cn', mode: 'popup', language: 'cn' };
  }
}

// In-memory cache + bridge to app.globalData
let _cached = null;

export function setCachedCaptchaConfig(cfg) {
  _cached = cfg;
  try {
    const app = getApp && getApp();
    if (app && app.globalData) app.globalData.captchaConfig = cfg;
  } catch (_) {}
}

export function getCachedCaptchaConfig() {
  if (_cached) return _cached;
  try {
    const app = getApp && getApp();
    if (app && app.globalData && app.globalData.captchaConfig) {
      _cached = app.globalData.captchaConfig;
      return _cached;
    }
  } catch (_) {}
  return null;
}

export async function ensureCaptchaConfig() {
  const cached = getCachedCaptchaConfig();
  if (cached) return cached;
  const cfg = await fetchCaptchaConfig();
  setCachedCaptchaConfig(cfg);
  return cfg;
}

export function initCaptcha(page, cfg, handlers) {
  const provider = (cfg?.provider || 'none').toLowerCase();
  page._captchaActive = false;
  page.setData({ captchaProvider: provider, captchaSceneId: cfg?.sceneId || '' });

  if (provider === 'aliyun' && cfg?.sceneId) {
    const success = handlers?.success || (() => {});
    const fail = handlers?.fail || (() => {});
    const onReady = handlers?.onReady || null;
    page.setData({
      pluginProps: {
        SceneId: cfg.sceneId,
        mode: cfg.mode || 'popup',
        language: cfg.language || 'cn',
        region: cfg.region || 'cn',
        success: (token) => { page._captchaActive = false; page._captchaRetryCount = 0; success(token); },
        fail: (err) => {
          // Robust fail handling: retry show once if active
          if (!page._captchaActive) { page._captchaRetryCount = 0; return; }
          try { page._captchaRetryCount = Number(page._captchaRetryCount || 0); } catch (_) { page._captchaRetryCount = 0; }
          try {
            const AliyunCaptcha = requirePlugin('AliyunCaptcha');
            if (page._captchaRetryCount < 1) {
              page._captchaRetryCount += 1;
              // Small delay before retrying show
              const retry = () => {
                try { AliyunCaptcha.show(); } catch (e) { /* swallow */ }
              };
              if (typeof wx.nextTick === 'function') wx.nextTick(() => setTimeout(retry, 200));
              else setTimeout(retry, 240);
              return; // don't propagate to page fail yet
            }
          } catch (_) { /* ignore */ }
          // After retry already attempted, propagate to page fail
          try { if (typeof fail === 'function') fail(err); } catch (_) {}
          page._captchaActive = false;
          page._captchaRetryCount = 0;
        }
      },
      loadCaptcha: true
    }, () => {
      // Mark ready after component mounted
      page._captchaReady = true;
      if (typeof onReady === 'function') {
        try { onReady(); } catch (e) { logger.error('captcha onReady error', { error: e.message || String(e) }); }
      }
    });
  }
}

export async function showCaptcha(page) {
  const provider = (page.data.captchaProvider || '').toLowerCase();
  if (provider !== 'aliyun') return;
  const sceneId = page.data.captchaSceneId;
  try { logger.debug('showCaptcha begin', { load: !!page.data.loadCaptcha, ready: !!page._captchaReady, scene: !!sceneId }); } catch (_) {}

  // If plugin not mounted/ready or missing SceneId, (re)init with cached config then show when ready
  if (!page.data.loadCaptcha || !sceneId || !page._captchaReady) {
    try {
      const cfg = getCachedCaptchaConfig() || await ensureCaptchaConfig();
      if (!cfg || cfg.provider !== 'aliyun' || !cfg.sceneId) return;
      try { logger.debug('showCaptcha path', { path: 'init' }); } catch (_) {}
      initCaptcha(page, cfg, {
        success: (token) => { page._captchaActive = false; page._captchaRetryCount = 0; if (page.onCaptchaSuccess) page.onCaptchaSuccess(token); },
        // Fail propagation will be handled inside initCaptcha with single retry
        fail: (/* err */) => { /* swallow here; page handler will be called only after retry fails */ },
        onReady: () => {
          // After mounted, show popup
          page._captchaActive = true;
          page._captchaRetryCount = 0;
          try {
            const AliyunCaptcha = requirePlugin('AliyunCaptcha');
            if (typeof wx.nextTick === 'function') {
              wx.nextTick(() => AliyunCaptcha.show());
            } else {
              setTimeout(() => AliyunCaptcha.show(), 0);
            }
          } catch (e) {
            logger.error('showCaptcha failed after init', { error: e.message || String(e) });
            page._captchaActive = false;
            page._captchaRetryCount = 0;
          }
        }
      });
      return; // Avoid calling show twice
    } catch (e) {
      logger.error('showCaptcha init failed', { error: e.message || String(e) });
      return;
    }
  }

  // Already mounted and ready
  page._captchaActive = true;
  page._captchaRetryCount = 0;
  try { logger.debug('showCaptcha path', { path: 'ready' }); } catch (_) {}
  try {
    const AliyunCaptcha = requirePlugin('AliyunCaptcha');
    if (typeof wx.nextTick === 'function') {
      wx.nextTick(() => AliyunCaptcha.show());
    } else {
      setTimeout(() => AliyunCaptcha.show(), 0);
    }
  } catch (e) {
    logger.error('showCaptcha failed', { error: e.message || String(e) });
    page._captchaActive = false;
    page._captchaRetryCount = 0;
  }
}

export default {
  fetchCaptchaConfig,
  setCachedCaptchaConfig,
  getCachedCaptchaConfig,
  ensureCaptchaConfig,
  initCaptcha,
  showCaptcha
};
