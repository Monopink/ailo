const INPUT_STATUSES = ['default', 'error', 'success', 'warning'] as const;
type InputStatus = (typeof INPUT_STATUSES)[number];

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
      value: '',
    },
    label: {
      type: String,
      value: '',
    },
    helperText: {
      type: String,
      value: '',
    },
    error: {
      type: String,
      value: '',
    },
    status: {
      type: String,
      value: 'default',
    },
    type: {
      type: String,
      value: 'text',
    },
    disabled: {
      type: Boolean,
      value: false,
    },
    readonly: {
      type: Boolean,
      value: false,
    },
    autoFocus: {
      type: Boolean,
      value: false,
    },
    confirmType: {
      type: String,
      value: 'done',
    },
    maxLength: {
      type: Number,
      value: 512,
    },
    borderless: {
      type: Boolean,
      value: false,
    },
  },
  data: {
    valueLength: 0,
  },
  observers: {
    status(value: string) {
      const normalized = INPUT_STATUSES.includes(value as InputStatus)
        ? (value as InputStatus)
        : 'default';
      if (normalized !== this.data.status) {
        this.setData({ status: normalized });
      }
    },
    value(newValue: string) {
      this.setData({ valueLength: (newValue || '').length });
    },
  },
  methods: {
    handleInput(event: WechatMiniprogram.Input) {
      const detailValue = event.detail?.value ?? '';
      this.triggerEvent('input', { value: detailValue }, { bubbles: true, composed: true });
    },
    handleFocus() {
      this.triggerEvent('focus');
    },
    handleBlur() {
      this.triggerEvent('blur');
    },
    handleConfirm(event: WechatMiniprogram.Input) {
      const detailValue = event.detail?.value ?? '';
      this.triggerEvent('confirm', { value: detailValue });
    },
  },
});
