Component({
  options: {
    addGlobalClass: true,
    multipleSlots: true,
  },
  properties: {
    type: {
      type: String,
      value: 'default',
    },
    variant: {
      type: String,
      value: 'solid',
    },
    size: {
      type: String,
      value: 'medium',
    },
  },
});
