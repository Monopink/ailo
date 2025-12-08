Component({
  options: {
    addGlobalClass: true,
  },
  properties: {
    count: {
      type: Number,
      value: 0,
    },
    dot: {
      type: Boolean,
      value: false,
    },
    max: {
      type: Number,
      value: 99,
    },
    showZero: {
      type: Boolean,
      value: false,
    },
  },
  data: {
    displayCount: '',
  },
  observers: {
    'count, max'(count: number, max: number) {
      if (typeof count !== 'number' || typeof max !== 'number') {
        this.setData({ displayCount: '' });
        return;
      }
      if (count > max) {
        this.setData({ displayCount: `${max}+` });
        return;
      }
      this.setData({ displayCount: `${Math.max(0, count)}` });
    },
  },
});
