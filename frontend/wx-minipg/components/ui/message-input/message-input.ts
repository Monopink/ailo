const DEFAULT_MAX_LENGTH = 500;

Component({
  options: {
    addGlobalClass: true,
  },
  properties: {
    value: {
      type: String,
      value: '',
    },
    placeholder: {
      type: String,
      value: '输入消息...',
    },
    disabled: {
      type: Boolean,
      value: false,
    },
    sending: {
      type: Boolean,
      value: false,
    },
    showEmoji: {
      type: Boolean,
      value: true,
    },
    showExtra: {
      type: Boolean,
      value: false,
    },
    maxLength: {
      type: Number,
      value: DEFAULT_MAX_LENGTH,
    },
    autoFocus: {
      type: Boolean,
      value: false,
    },
  },
  methods: {
    handleInput(event: WechatMiniprogram.Input) {
      const value = event.detail?.value ?? '';
      this.triggerEvent('input', { value }, { bubbles: true, composed: true });
    },
    handleFocus() {
      this.triggerEvent('focus');
    },
    handleBlur() {
      this.triggerEvent('blur');
    },
    handleConfirm(event: WechatMiniprogram.Input) {
      const value = event.detail?.value ?? '';
      this.triggerEvent('confirm', { value });
    },
    handleSend() {
      if (this.data.disabled || this.data.sending || !this.data.value) {
        return;
      }
      this.triggerEvent('send', { value: this.data.value });
    },
    handleEmojiTap() {
      if (!this.data.showEmoji) {
        return;
      }
      this.triggerEvent('emojiTap');
    },
    handleExtraTap() {
      if (!this.data.showExtra) {
        return;
      }
      this.triggerEvent('extraTap');
    },
  },
});
