Component({
  options: {
    addGlobalClass: true,
  },
  properties: {
    checked: {
      type: Boolean,
      value: false,
    },
    disabled: {
      type: Boolean,
      value: false,
    },
  },
  methods: {
    toggle() {
      if (this.data.disabled) {
        return;
      }
      const nextValue = !this.data.checked;
      this.setData({ checked: nextValue });
      this.triggerEvent('change', { value: nextValue }, { bubbles: true, composed: true });
    },
  },
});
