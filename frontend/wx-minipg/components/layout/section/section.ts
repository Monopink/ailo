/**
 * Layout Section Component
 *
 * Groups related content with consistent spacing and optional styling.
 * Used within pages to create visual hierarchy and organization.
 *
 * Properties:
 * - title: string
 * - spacing: 'none' | 'small' | 'medium' | 'large'
 * - background: 'transparent' | 'card' | 'tertiary'
 * - rounded: boolean
 * - shadow: boolean
 */

Component({
  options: {
    multipleSlots: true,
    styleIsolation: 'apply-shared',
  },

  properties: {
    title: {
      type: String,
      value: '',
    },
    spacing: {
      type: String,
      value: 'medium',
    },
    background: {
      type: String,
      value: 'transparent',
    },
    rounded: {
      type: Boolean,
      value: false,
    },
    shadow: {
      type: Boolean,
      value: false,
    },
  },

  data: {
    hasHeader: false,
    hasFooter: false,
  },

  lifetimes: {
    attached() {
      // Check if slots are used
      // Note: WeChat miniprogram doesn't provide direct slot detection
      // This is a placeholder for future enhancement
      this.setData({
        hasHeader: false,
        hasFooter: false,
      });
    },
  },
});
