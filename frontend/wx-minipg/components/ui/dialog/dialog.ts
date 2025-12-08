interface DialogButton {
  text: string;
  type?: 'primary' | 'secondary' | 'danger';
  action?: string;
}

Component({
  options: {
    addGlobalClass: true,
    multipleSlots: true,
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
    content: {
      type: String,
      value: '',
    },
    buttons: {
      type: Array,
      value: [] as DialogButton[],
    },
    maskClosable: {
      type: Boolean,
      value: true,
    },
  },
  methods: {
    handleMaskTap() {
      if (!this.data.maskClosable) {
        return;
      }
      this.triggerEvent('close');
    },
    handleButtonTap(event: WechatMiniprogram.BaseEvent) {
      const index = Number(event.currentTarget.dataset.index);
      const button = (this.data.buttons ?? [])[index] as DialogButton | undefined;
      this.triggerEvent('buttontap', { index, button });
    },
  },
});
