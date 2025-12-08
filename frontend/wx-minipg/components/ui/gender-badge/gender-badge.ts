Component({
  options: {
    addGlobalClass: true,
  },
  properties: {
    gender: {
      type: Number,
      value: 0, // 0: unknown, 1: male, 2: female, 3: other
      observer(newVal) {
        this.updateGenderSymbol(newVal);
      },
    },
  },
  data: {
    genderSymbol: '',
  },
  lifetimes: {
    attached() {
      this.updateGenderSymbol(this.data.gender);
    },
  },
  methods: {
    updateGenderSymbol(gender: number) {
      const symbols: Record<number, string> = {
        0: '?',
        1: '♂', // Male
        2: '♀', // Female
        3: '⚧', // Other/Non-binary
        4: '?',
      };
      this.setData({
        genderSymbol: symbols[gender] || '?',
      });
    },
  },
});
