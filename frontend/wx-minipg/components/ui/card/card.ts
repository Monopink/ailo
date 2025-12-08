/**
 * Card Component
 *
 * A versatile container component with consistent styling.
 * Provides elevation through shadows and supports various padding options.
 *
 * Properties:
 * - padding: 'none' | 'small' | 'medium' | 'large'
 * - shadow: boolean
 * - bordered: boolean
 * - hoverable: boolean
 */

Component({
  options: {
    multipleSlots: true,
    styleIsolation: 'apply-shared',
  },

  properties: {
    padding: {
      type: String,
      value: 'medium',
    },
    shadow: {
      type: Boolean,
      value: true,
    },
    bordered: {
      type: Boolean,
      value: false,
    },
    hoverable: {
      type: Boolean,
      value: false,
    },
    hasHeader: {
      type: Boolean,
      value: false,
    },
    hasFooter: {
      type: Boolean,
      value: false,
    },
  },

  methods: {
    onCardTap() {
      if (this.data.hoverable) {
        this.triggerEvent('tap');
      }
    },
  },
});
