// Gender values: 1 = male, 2 = female, others = unknown
const GENDER_ICON_MAP: Record<number, string | undefined> = {
  1: 'gender-male',
  2: 'gender-female',
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
    iconName: '',
  },

  observers: {
    gender(value: number) {
      const iconName = GENDER_ICON_MAP[value];
      this.setData({ iconName: iconName ?? '' });
    },
  },
});
