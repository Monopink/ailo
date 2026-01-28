/**
 * Page Layout Component
 *
 * Standard page structure component for all pages.
 * Handles loading, error, and empty states automatically.
 */

Component({
  options: {
    multipleSlots: true, // Enable multiple named slots
  },

  properties: {
    isLoading: {
      type: Boolean,
      value: false,
    },
    hasError: {
      type: Boolean,
      value: false,
    },
    errorMessage: {
      type: String,
      value: '',
    },
    isEmpty: {
      type: Boolean,
      value: false,
    },
    emptyMessage: {
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

  observers: {
    'headerSolidMode,headerSolid'(headerSolidMode: string, headerSolid: boolean) {
      if (headerSolidMode === 'manual') {
        this.setData({ isHeaderSolid: headerSolid });
      }
    },
  },

  methods: {
    /**
     * Handle retry button click in error state
     */
    onRetryClick() {
      this.triggerEvent('retry');
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
