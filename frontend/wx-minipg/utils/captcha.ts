/**
 * Aliyun Captcha Integration Utility
 *
 * CRITICAL PATTERN (do not modify during refactoring):
 * 1. WXML: Component MUST use `wx:if="{{loadCaptcha}}"`, NO event bindings
 * 2. Data: Include all CaptchaPageData fields (captchaProvider, captchaSceneId, loadCaptcha, pluginProps)
 * 3. Display: Call `requirePlugin('AliyunCaptcha').show()`, NOT component methods
 * 4. Callbacks: Pass via pluginProps in initCaptcha(), NOT WXML bindings
 */

import { get } from './api';
import { getLogger } from './logger';

const logger = getLogger('CaptchaUtil');

type CaptchaConfig = Says.CaptchaConfig;
type CaptchaHandlers = Says.CaptchaHandlers;
type CaptchaPageInstance = Says.CaptchaPageInstance;

interface CaptchaConfigResponse {
  provider?: string;
  scene_id?: string;
  region?: string;
  mode?: string;
  language?: string;
}

let cachedConfig: CaptchaConfig | null = null;

const getDefaultConfig = (): CaptchaConfig => ({
  provider: 'none',
  sceneId: '',
  region: 'cn',
  mode: 'popup',
  language: 'cn',
});

export async function fetchCaptchaConfig(): Promise<CaptchaConfig> {
  try {
    const cfg = await get<CaptchaConfigResponse>('/system/captcha-config', {}, { auth: false });
    return {
      provider: cfg.provider || 'none',
      sceneId: cfg.scene_id || '',
      region: cfg.region || 'cn',
      mode: cfg.mode || 'popup',
      language: cfg.language || 'cn',
    };
  } catch (error) {
    logger.error('fetchCaptchaConfig failed', { error });
    return getDefaultConfig();
  }
}

export function setCachedCaptchaConfig(cfg: CaptchaConfig): void {
  cachedConfig = cfg;
  try {
    const app = getApp<SaysAppInstance>();
    if (app && app.globalData) {
      app.globalData.captchaConfig = cfg;
    }
  } catch (_) {
    // ignore
  }
}

export function getCachedCaptchaConfig(): CaptchaConfig | null {
  if (cachedConfig) {
    return cachedConfig;
  }
  try {
    const app = getApp<SaysAppInstance>();
    const config = app?.globalData?.captchaConfig;
    if (config) {
      cachedConfig = config;
      return cachedConfig;
    }
  } catch (_) {
    // ignore
  }
  return null;
}

export async function ensureCaptchaConfig(): Promise<CaptchaConfig> {
  const cached = getCachedCaptchaConfig();
  if (cached) {
    return cached;
  }
  const cfg = await fetchCaptchaConfig();
  setCachedCaptchaConfig(cfg);
  return cfg;
}

export function initCaptcha(
  page: CaptchaPageInstance,
  cfg: CaptchaConfig,
  handlers?: CaptchaHandlers
): void {
  const provider = (cfg?.provider || 'none').toLowerCase();
  page._captchaActive = false;
  page.setData({ captchaProvider: provider, captchaSceneId: cfg?.sceneId || '' });

  if (provider === 'aliyun' && cfg?.sceneId) {
    const success = handlers?.success
      ? (token: string) => handlers.success?.(token)
      : () => undefined;
    const fail = handlers?.fail ? (error: unknown) => handlers.fail?.(error) : () => undefined;
    const onReady = handlers?.onReady ? () => handlers.onReady?.() : null;
    page.setData(
      {
        pluginProps: {
          SceneId: cfg.sceneId,
          mode: cfg.mode || 'popup',
          language: cfg.language || 'cn',
          region: cfg.region || 'cn',
          success: (token: string) => {
            page._captchaActive = false;
            page._captchaRetryCount = 0;
            success(token);
          },
          fail: (err: unknown) => {
            // Robust fail handling: retry show once if active
            if (!page._captchaActive) {
              page._captchaRetryCount = 0;
              return;
            }
            page._captchaRetryCount = Number(page._captchaRetryCount || 0);
            try {
              const AliyunCaptcha = requirePlugin('AliyunCaptcha') as { show: () => void };
              if ((page._captchaRetryCount || 0) < 1) {
                page._captchaRetryCount = (page._captchaRetryCount || 0) + 1;
                const retry = (): void => {
                  try {
                    AliyunCaptcha.show();
                  } catch {
                    /* ignore */
                  }
                };
                if (typeof wx.nextTick === 'function') {
                  wx.nextTick(() => setTimeout(retry, 200));
                } else {
                  setTimeout(retry, 240);
                }
                return;
              }
            } catch {
              // ignore
            }
            try {
              fail(err);
            } catch {
              // ignore
            }
            page._captchaActive = false;
            page._captchaRetryCount = 0;
          },
        },
        loadCaptcha: true,
      },
      () => {
        page._captchaReady = true;
        if (typeof onReady === 'function') {
          try {
            onReady();
          } catch (error) {
            logger.error('captcha onReady error', { error });
          }
        }
      }
    );
  }
}

export async function showCaptcha(page: CaptchaPageInstance): Promise<void> {
  const provider = (page.data.captchaProvider || '').toLowerCase();
  if (provider !== 'aliyun') {
    return;
  }
  const sceneId = page.data.captchaSceneId;
  try {
    logger.debug('showCaptcha begin', {
      load: Boolean(page.data.loadCaptcha),
      ready: Boolean(page._captchaReady),
      scene: Boolean(sceneId),
    });
  } catch {
    // ignore
  }

  // If plugin not mounted/ready or missing SceneId, (re)init with cached config then show when ready
  if (!page.data.loadCaptcha || !sceneId || !page._captchaReady) {
    try {
      const cfg = getCachedCaptchaConfig() || (await ensureCaptchaConfig());
      if (!cfg || cfg.provider !== 'aliyun' || !cfg.sceneId) {
        return;
      }
      try {
        logger.debug('showCaptcha path', { path: 'init' });
      } catch {
        // ignore
      }
      initCaptcha(page, cfg, {
        success: (token: string) => {
          page._captchaActive = false;
          page._captchaRetryCount = 0;
          if (typeof page.onCaptchaSuccess === 'function') {
            page.onCaptchaSuccess(token);
          }
        },
        fail: () => undefined,
        onReady: () => {
          // After mounted, show popup
          page._captchaActive = true;
          page._captchaRetryCount = 0;
          try {
            const AliyunCaptcha = requirePlugin('AliyunCaptcha') as { show: () => void };
            if (typeof wx.nextTick === 'function') {
              wx.nextTick(() => AliyunCaptcha.show());
            } else {
              setTimeout(() => AliyunCaptcha.show(), 0);
            }
          } catch (error) {
            logger.error('showCaptcha failed after init', { error });
            page._captchaActive = false;
            page._captchaRetryCount = 0;
          }
        },
      });
      return; // Avoid calling show twice
    } catch (error) {
      logger.error('showCaptcha init failed', { error });
      return;
    }
  }

  // Already mounted and ready
  page._captchaActive = true;
  page._captchaRetryCount = 0;
  try {
    logger.debug('showCaptcha path', { path: 'ready' });
  } catch {
    // ignore
  }
  try {
    const AliyunCaptcha = requirePlugin('AliyunCaptcha') as { show: () => void };
    if (typeof wx.nextTick === 'function') {
      wx.nextTick(() => AliyunCaptcha.show());
    } else {
      setTimeout(() => AliyunCaptcha.show(), 0);
    }
  } catch (error) {
    logger.error('showCaptcha failed', { error });
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
  showCaptcha,
};
