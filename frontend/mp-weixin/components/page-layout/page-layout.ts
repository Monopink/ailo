/**
 * Page Layout Component
 *
 * Standard page structure component for all pages.
 * State source of truth is screenModel contract.
 */

const VALID_SCREEN_STATES = new Set(['booting', 'ready']);
const VALID_CONTENT_VARIANTS = new Set(['data', 'empty', 'blank']);
const VALID_REFRESH_STATES = new Set(['idle', 'refreshing', 'degraded']);
const VALID_THEME_MODES = new Set(['system', 'fixed-light', 'fixed-dark']);

const normalizeThemeMode = (input: string): 'system' | 'fixed-light' | 'fixed-dark' => {
  if (VALID_THEME_MODES.has(input)) {
    return input as 'system' | 'fixed-light' | 'fixed-dark';
  }
  return 'system';
};

const getThemeClassName = (themeMode: 'system' | 'fixed-light' | 'fixed-dark'): string => {
  if (themeMode === 'fixed-light') {
    return 'page-layout--theme-fixed-light';
  }
  if (themeMode === 'fixed-dark') {
    return 'page-layout--theme-fixed-dark';
  }
  return '';
};

const reportInvalidScreenModel = (input: {
  screenState: string;
  contentVariant: string;
  refreshState: string;
}): void => {
  if (
    VALID_SCREEN_STATES.has(input.screenState) &&
    VALID_CONTENT_VARIANTS.has(input.contentVariant) &&
    VALID_REFRESH_STATES.has(input.refreshState)
  ) {
    return;
  }
  console.error('[page-layout] invalid screen model', input);
};

Component({
  options: {
    multipleSlots: true, // Enable multiple named slots
  },

  properties: {
    screenState: {
      type: String,
      value: '',
    },
    contentVariant: {
      type: String,
      value: '',
    },
    refreshState: {
      type: String,
      value: '',
    },
    emptyMessage: {
      type: String,
      value: '',
    },
    emptyActionText: {
      type: String,
      value: '',
    },
    hasFooter: {
      type: Boolean,
      value: false,
    },
    fixedFooter: {
      type: Boolean,
      value: false,
    },
    contentScrollIntoView: {
      type: String,
      value: '',
    },
    contentScrollWithAnimation: {
      type: Boolean,
      value: true,
    },
    lowerThreshold: {
      type: Number,
      value: 200,
    },
    enableContentRefresh: {
      type: Boolean,
      value: false,
    },
    disableScroll: {
      type: Boolean,
      value: false,
    },
    headerSolidMode: {
      type: String,
      value: 'auto',
    },
    headerSolid: {
      type: Boolean,
      value: false,
    },
    headerSolidThreshold: {
      type: Number,
      value: 12,
    },
    themeMode: {
      type: String,
      value: 'system',
    },
  },

  data: {
    isHeaderSolid: false,
    themeClassName: '',
  },

  lifetimes: {
    attached() {
      this.validateScreenModel();
      this.syncThemeMode(this.properties.themeMode);
    },
  },

  observers: {
    'headerSolidMode,headerSolid'(headerSolidMode: string, headerSolid: boolean) {
      if (headerSolidMode === 'manual') {
        this.setData({ isHeaderSolid: headerSolid });
      }
    },
    'screenState,contentVariant,refreshState'() {
      this.validateScreenModel();
    },
    themeMode(themeMode: string) {
      this.syncThemeMode(themeMode);
    },
  },

  methods: {
    validateScreenModel() {
      reportInvalidScreenModel({
        screenState: this.properties.screenState,
        contentVariant: this.properties.contentVariant,
        refreshState: this.properties.refreshState,
      });
    },

    syncThemeMode(themeMode: string) {
      const normalizedThemeMode = normalizeThemeMode(themeMode);
      const themeClassName = getThemeClassName(normalizedThemeMode);
      if (this.data.themeClassName === themeClassName) {
        return;
      }
      this.setData({ themeClassName });
    },

    onEmptyAction() {
      this.triggerEvent('emptyaction');
    },

    onContentScroll(event: WechatMiniprogram.ScrollViewScroll) {
      this.triggerEvent('contentscroll', {
        scrollTop: event.detail.scrollTop,
      });
      if (this.properties.headerSolidMode !== 'auto') {
        return;
      }
      const scrollTop = Math.max(0, Math.round(event.detail.scrollTop));
      const shouldSolid = scrollTop > this.properties.headerSolidThreshold;
      if (shouldSolid !== this.data.isHeaderSolid) {
        this.setData({ isHeaderSolid: shouldSolid });
      }
    },

    onContentReachBottom() {
      this.triggerEvent('contentreachbottom');
    },

    onContentRefresh() {
      this.triggerEvent('contentrefresh');
    },

    onContentRefresherRestore() {
      this.triggerEvent('contentrefresherrestore');
    },
  },
});
