Component({
  options: {
    addGlobalClass: true,
  },
  properties: {
    type: {
      type: String,
      value: 'empty',
    },
    message: {
      type: String,
      value: '暂无数据',
    },
    actionText: {
      type: String,
      value: '',
    },
  },
  methods: {
    handleAction() {
      this.triggerEvent('action');
    },
  },
});
