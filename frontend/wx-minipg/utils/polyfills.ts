import { getLogger } from './logger';
import { isNonEmptyString } from './guards';

const logger = getLogger('Polyfills');

type WxWithBaseInfo = typeof wx & {
  getAppBaseInfo?: () => WechatMiniprogram.AppBaseInfo;
  getAppBaseInfoSync?: () => WechatMiniprogram.AppBaseInfo;
};

let appBaseInfoPatched = false;

const buildFallbackAppBaseInfo = (): WechatMiniprogram.AppBaseInfo => {
  try {
    const systemInfo: WechatMiniprogram.SystemInfo = wx.getSystemInfoSync();
    const sdkVersion = isNonEmptyString(systemInfo.SDKVersion)
      ? systemInfo.SDKVersion
      : isNonEmptyString(systemInfo.version)
        ? systemInfo.version
        : '';
    const version = isNonEmptyString(systemInfo.version)
      ? systemInfo.version
      : isNonEmptyString(systemInfo.SDKVersion)
        ? systemInfo.SDKVersion
        : '';
    const language = isNonEmptyString(systemInfo.language) ? systemInfo.language : 'zh_CN';
    const fontSizeSettingCandidate = (systemInfo as { fontSizeSetting?: number }).fontSizeSetting;
    const fontSizeScaleFactorCandidate = (systemInfo as { fontSizeScaleFactor?: number })
      .fontSizeScaleFactor;
    return {
      SDKVersion: sdkVersion,
      version,
      language,
      enableDebug: (systemInfo as { enableDebug?: boolean }).enableDebug === true,
      fontSizeSetting: typeof fontSizeSettingCandidate === 'number' ? fontSizeSettingCandidate : 16,
      fontSizeScaleFactor:
        typeof fontSizeScaleFactorCandidate === 'number'
          ? fontSizeScaleFactorCandidate
          : typeof fontSizeSettingCandidate === 'number'
            ? fontSizeSettingCandidate / 16
            : 1,
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
