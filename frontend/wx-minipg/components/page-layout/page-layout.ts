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
  },

  methods: {
    /**
     * Handle retry button click in error state
     */
    onRetryClick() {
      this.triggerEvent('retry');
    },
  },
});
