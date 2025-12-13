import {
  getDefaultCountry,
  formatPhoneWithCountryCode,
  validatePhoneLength,
} from '../../../utils/country-codes';

Component({
  options: {
    styleIsolation: 'apply-shared',
  },

  properties: {
    value: {
      type: String,
      value: '',
    },
    placeholder: {
      type: String,
      value: '请输入手机号',
    },
    disabled: {
      type: Boolean,
      value: false,
    },
  },

  data: {
    countryCode: '+86',
    phoneMaxLength: 11,
  },

  lifetimes: {
    attached() {
      // Fixed to China Mainland (+86)
      const defaultCountry = getDefaultCountry();
      this.setData({
        countryCode: defaultCountry.code,
        phoneMaxLength: defaultCountry.phoneLength,
      });
    },
  },

  methods: {
    handleInput(event: WechatMiniprogram.CustomEvent<{ value: string }>) {
      const value = event.detail.value;
      const isValid = validatePhoneLength(this.data.countryCode, value);

      this.triggerEvent('change', {
        value,
        countryCode: this.data.countryCode,
        fullPhone: formatPhoneWithCountryCode(this.data.countryCode, value),
        valid: isValid,
      });
    },

    handleFocus(event: WechatMiniprogram.CustomEvent) {
      this.triggerEvent('focus', event.detail);
    },

    handleBlur(event: WechatMiniprogram.CustomEvent) {
      this.triggerEvent('blur', event.detail);
    },

    // Public method: get full phone number
    getFullPhone(): string {
      return formatPhoneWithCountryCode(this.data.countryCode, this.data.value);
    },

    // Public method: validate
    validate(): boolean {
      return validatePhoneLength(this.data.countryCode, this.data.value);
    },
  },
});
