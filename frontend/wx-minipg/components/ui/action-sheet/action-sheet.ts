/**
 * Action Sheet Component
 *
 * iOS-style bottom sheet menu with actions.
 * Displays a list of actions that slide up from the bottom.
 */

interface ActionItem {
  text: string;
  type?: 'default' | 'destructive';
  disabled?: boolean;
}

Component({
  options: {
    styleIsolation: 'apply-shared',
  },

  properties: {
    show: {
      type: Boolean,
      value: false,
    },
    title: {
      type: String,
      value: '',
    },
    actions: {
      type: Array,
      value: [],
    },
    cancelText: {
      type: String,
      value: '取消',
    },
    maskClosable: {
      type: Boolean,
      value: true,
    },
  },

  data: {
    animationClass: '',
  },

  observers: {
    show(newVal: boolean) {
      if (newVal) {
        this.setData({ animationClass: 'ui-action-sheet--show' });
      } else {
        this.setData({ animationClass: '' });
      }
    },
  },

  methods: {
    onMaskTap() {
      if (this.data.maskClosable) {
        this.close();
      }
    },

    onActionTap(e: WechatMiniprogram.TouchEvent) {
      const dataset = e.currentTarget.dataset as { index?: number };
      const index = dataset.index;

      if (typeof index !== 'number') {
        return;
      }

      const action = this.data.actions[index] as ActionItem | undefined;
      if (!action || action.disabled) {
        return;
      }

      this.triggerEvent('select', { index, action });
      this.close();
    },

    onCancelTap() {
      this.triggerEvent('cancel');
      this.close();
    },

    close() {
      this.triggerEvent('close');
    },

    // Prevent touch events from bubbling to mask
    preventTap() {
      // Do nothing, just prevent bubbling
    },
  },
});
