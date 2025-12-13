// Gender values: 1 = male, 2 = female, others = unknown
const GENDER_MAP: Record<number, string> = {
  1: '♂',
  2: '♀',
};

Component({
  options: {
    addGlobalClass: true,
    styleIsolation: 'apply-shared',
  },

  properties: {
    gender: {
      type: Number,
      value: 0,
    },
  },

  data: {
    icon: '',
  },

  observers: {
    gender(value: number) {
      this.setData({ icon: GENDER_MAP[value] || '' });
    },
  },
});
