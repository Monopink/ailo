/**
 * Layout Container Component
 *
 * Provides consistent page-level container with configurable padding and background.
 * This is the outermost layout component for pages.
 *
 * Properties:
 * - padding: 'none' | 'small' | 'medium' | 'large'
 * - background: 'primary' | 'secondary' | 'tertiary'
 */

Component({
  options: {
    multipleSlots: false,
    styleIsolation: 'apply-shared',
  },

  properties: {
    padding: {
      type: String,
      value: 'medium',
    },
    background: {
      type: String,
      value: 'primary',
    },
  },
});
