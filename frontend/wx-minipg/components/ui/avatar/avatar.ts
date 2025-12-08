Component({
  options: {
    addGlobalClass: true,
  },
  data: {
    hasError: false,
  },
  properties: {
    src: {
      type: String,
      value: '',
    },
    size: {
      type: String,
      value: 'medium',
    },
    shape: {
      type: String,
      value: 'square',
    },
    gender: {
      type: String,
      value: '',
    },
  },
  methods: {
    handleError() {
      this.setData({ hasError: true });
    },
    handleLoad() {
      if (this.data.hasError) {
        this.setData({ hasError: false });
      }
    },
  },
});
