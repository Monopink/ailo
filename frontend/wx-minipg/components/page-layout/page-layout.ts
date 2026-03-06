/**
 * Page Layout Component
 *
 * Standard page structure component for all pages.
 * State source of truth is screenModel contract.
 */

const VALID_SCREEN_STATES = new Set(['booting', 'ready']);
const VALID_CONTENT_VARIANTS = new Set(['data', 'empty', 'blank']);
const VALID_REFRESH_STATES = new Set(['idle', 'refreshing', 'degraded']);

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
  },

  data: {
    isHeaderSolid: false,
  },

  lifetimes: {
    attached() {
      this.validateScreenModel();
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
  },

  methods: {
    validateScreenModel() {
      reportInvalidScreenModel({
        screenState: this.properties.screenState,
        contentVariant: this.properties.contentVariant,
        refreshState: this.properties.refreshState,
      });
    },

    onEmptyAction() {
      this.triggerEvent('emptyaction');
    },

    onContentScroll(event: WechatMiniprogram.ScrollViewScroll) {
      if (this.properties.headerSolidMode !== 'auto') {
        return;
      }
      const scrollTop = Math.max(0, Math.round(event.detail.scrollTop));
      const shouldSolid = scrollTop > this.properties.headerSolidThreshold;
      if (shouldSolid !== this.data.isHeaderSolid) {
        this.setData({ isHeaderSolid: shouldSolid });
      }
    },
  },
});
