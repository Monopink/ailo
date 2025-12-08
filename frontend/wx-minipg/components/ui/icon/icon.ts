/**
 * Icon Component
 *
 * Displays icons using CSS-based graphics.
 * Currently supports: more-horizontal (three dots)
 *
 * Properties:
 * - name: 'more-horizontal'
 * - size: 'small' | 'medium' | 'large'
 * - color: 'primary' | 'secondary' | 'tertiary'
 */

Component({
  options: {
    styleIsolation: 'apply-shared',
  },

  properties: {
    name: {
      type: String,
      value: 'more-horizontal',
    },
    size: {
      type: String,
      value: 'medium',
    },
    color: {
      type: String,
      value: 'secondary',
    },
  },
});
