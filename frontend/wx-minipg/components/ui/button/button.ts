const BUTTON_TYPES = ['primary', 'secondary', 'danger', 'text'] as const;
const BUTTON_SIZES = ['small', 'medium', 'large'] as const;

type ButtonType = (typeof BUTTON_TYPES)[number];
type ButtonSize = (typeof BUTTON_SIZES)[number];

Component({
  options: {
    addGlobalClass: true,
    multipleSlots: true,
  },
  properties: {
    type: {
      type: String,
      value: 'primary',
    },
    size: {
      type: String,
      value: 'medium',
    },
    block: {
      type: Boolean,
      value: false,
    },
    disabled: {
      type: Boolean,
      value: false,
    },
    loading: {
      type: Boolean,
      value: false,
    },
    // Support WeChat native button open-type
    openType: {
      type: String,
      value: '',
    },
  },
  methods: {
    handleTap(event: WechatMiniprogram.TouchEvent) {
      const type = (this.data.type ?? 'primary') as ButtonType;
      const size = (this.data.size ?? 'medium') as ButtonSize;
      if (!BUTTON_TYPES.includes(type) || !BUTTON_SIZES.includes(size)) {
        return;
      }
      if (this.data.disabled || this.data.loading) {
        return;
      }
      this.triggerEvent('tap', event.detail, { bubbles: true, composed: true });
    },
    // Forward native button events to parent component
    handleGetPhoneNumber(event: WechatMiniprogram.ButtonGetPhoneNumber) {
      this.triggerEvent('getphonenumber', event.detail);
    },
    handleContact(event: WechatMiniprogram.ButtonContact) {
      this.triggerEvent('contact', event.detail);
    },
    handleGetUserInfo(event: WechatMiniprogram.ButtonGetUserInfo) {
      this.triggerEvent('getuserinfo', event.detail);
    },
    handleOpenSetting(event: WechatMiniprogram.ButtonOpenSetting) {
      this.triggerEvent('opensetting', event.detail);
    },
    handleError(event: WechatMiniprogram.ButtonError) {
      this.triggerEvent('error', event.detail);
    },
  },
});
