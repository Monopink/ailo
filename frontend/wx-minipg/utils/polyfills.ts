import { getLogger } from './logger';

const logger = getLogger('Polyfills');

type WxWithBaseInfo = typeof wx & {
  getAppBaseInfo?: () => WechatMiniprogram.AppBaseInfo;
  getAppBaseInfoSync?: () => WechatMiniprogram.AppBaseInfo;
};

let appBaseInfoPatched = false;

const buildFallbackAppBaseInfo = (): WechatMiniprogram.AppBaseInfo => {
  try {
    const systemInfo = wx.getSystemInfoSync();
    return {
      SDKVersion: systemInfo.SDKVersion || systemInfo.version || '',
      version: systemInfo.version || systemInfo.SDKVersion || '',
      language: systemInfo.language || 'zh_CN',
      enableDebug: Boolean((systemInfo as { enableDebug?: boolean }).enableDebug),
      fontSizeSetting: systemInfo.fontSizeSetting ?? 16,
      fontSizeScaleFactor:
        (systemInfo as { fontSizeScaleFactor?: number }).fontSizeScaleFactor ??
        (typeof systemInfo.fontSizeSetting === 'number' ? systemInfo.fontSizeSetting / 16 : 1),
      host: { appId: '' },
      theme: (systemInfo as { theme?: 'light' | 'dark' }).theme,
    };
  } catch {
    return {
      SDKVersion: '0.0.0',
      version: '0.0.0',
      language: 'zh_CN',
      enableDebug: false,
      fontSizeSetting: 16,
      fontSizeScaleFactor: 1,
      host: { appId: '' },
    };
  }
};

export const ensureAppBaseInfoPolyfill = (): void => {
  const wxWithPolyfill = wx as WxWithBaseInfo;
  const hasAsync = typeof wxWithPolyfill.getAppBaseInfo === 'function';
  const hasSync = typeof wxWithPolyfill.getAppBaseInfoSync === 'function';

  if (hasAsync && hasSync) {
    return;
  }

  const fallbackInfo = buildFallbackAppBaseInfo();

  if (!hasAsync) {
    wxWithPolyfill.getAppBaseInfo = () => fallbackInfo;
  }

  if (!hasSync) {
    wxWithPolyfill.getAppBaseInfoSync = () => fallbackInfo;
  }

  if (!appBaseInfoPatched) {
    appBaseInfoPatched = true;
    logger.info('Polyfilled wx.getAppBaseInfo APIs for legacy base library');
  }
};

export const applyGlobalPolyfills = (): void => {
  ensureAppBaseInfoPolyfill();
};

applyGlobalPolyfills();
