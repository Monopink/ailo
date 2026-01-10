// Gender values: 1 = male, 2 = female, others = unknown
const GENDER_MAP: Record<number, string | undefined> = {
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
      const icon = GENDER_MAP[value];
      this.setData({ icon: icon ?? '' });
    },
  },
});
