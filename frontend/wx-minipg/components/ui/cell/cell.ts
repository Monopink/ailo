Component({
  options: {
    addGlobalClass: true,
    multipleSlots: true,
  },
  properties: {
    title: {
      type: String,
      value: '',
    },
    label: {
      type: String,
      value: '',
    },
    value: {
      type: String,
      value: '',
    },
    icon: {
      type: String,
      value: '',
    },
    link: {
      type: Boolean,
      value: false,
    },
    hover: {
      type: Boolean,
      value: true,
    },
  },
  methods: {
    handleTap(event: WechatMiniprogram.TouchEvent) {
      this.triggerEvent('tap', event.detail, { bubbles: true, composed: true });
    },
  },
});
