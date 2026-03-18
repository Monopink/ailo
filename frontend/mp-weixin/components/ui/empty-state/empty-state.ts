Component({
  options: {
    addGlobalClass: true,
    styleIsolation: 'apply-shared',
  },

  properties: {
    message: {
      type: String,
      value: '',
    },
    actionText: {
      type: String,
      value: '',
    },
  },

  data: {
    hasAction: false,
  },

  observers: {
    actionText(actionText: string) {
      const hasAction = typeof actionText === 'string' && actionText.trim().length > 0;
      this.setData({ hasAction });
    },
  },

  methods: {
    onActionTap() {
      this.triggerEvent('action');
    },
  },
});
