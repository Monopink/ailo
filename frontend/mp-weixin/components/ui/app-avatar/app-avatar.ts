const AVATAR_PRESET_SIZE = {
  small: '80rpx',
  medium: '96rpx',
  large: '128rpx',
} as const;

type AvatarPresetSize = keyof typeof AVATAR_PRESET_SIZE;

type AvatarComponentData = {
  sizeStyle: string;
  desiredSrc: string;
  mainSrc: string;
  mainFailed: boolean;
  prefetchSrc: string;
  prefetchFailed: boolean;
};

const DEFAULT_SIZE_STYLE = `width:${AVATAR_PRESET_SIZE.medium};height:${AVATAR_PRESET_SIZE.medium};`;

const resolveSizeStyle = (size: unknown): string => {
  if (typeof size === 'number' && Number.isFinite(size)) {
    const normalized = Math.max(1, Math.floor(size));
    return `width:${normalized}rpx;height:${normalized}rpx;`;
  }

  if (typeof size !== 'string') {
    return DEFAULT_SIZE_STYLE;
  }

  const preset = AVATAR_PRESET_SIZE[size as AvatarPresetSize];
  if (typeof preset === 'string') {
    return `width:${preset};height:${preset};`;
  }

  if (/^\d+(rpx|px)$/u.test(size)) {
    return `width:${size};height:${size};`;
  }

  return DEFAULT_SIZE_STYLE;
};

const resolveNonEmptyString = (value: unknown): string => {
  if (typeof value !== 'string') {
    return '';
  }
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : '';
};

Component({
  options: {
    addGlobalClass: true,
    styleIsolation: 'apply-shared',
  },

  properties: {
    src: {
      type: String,
      value: '',
    },
    size: {
      type: null,
      value: 'medium',
    },
    shape: {
      type: String,
      value: 'circle',
    },
    mode: {
      type: String,
      value: 'aspectFill',
    },
    webp: {
      type: Boolean,
      value: true,
    },
    lazy: {
      type: Boolean,
      value: false,
    },
  },

  data: {
    sizeStyle: DEFAULT_SIZE_STYLE,
    desiredSrc: '',
    mainSrc: '',
    mainFailed: false,
    prefetchSrc: '',
    prefetchFailed: false,
  } as AvatarComponentData,

  lifetimes: {
    attached() {
      this.syncFromProperties();
    },
  },

  observers: {
    'src,size'() {
      this.syncFromProperties();
    },
  },

  methods: {
    syncFromProperties() {
      const desiredSrc = resolveNonEmptyString(this.data.src);
      const sizeStyle = resolveSizeStyle(this.data.size);
      const basePatch: Partial<AvatarComponentData> = {};

      if (this.data.sizeStyle !== sizeStyle) {
        basePatch.sizeStyle = sizeStyle;
      }

      if (desiredSrc === '') {
        this.setData({
          ...basePatch,
          desiredSrc: '',
          mainSrc: '',
          mainFailed: false,
          prefetchSrc: '',
          prefetchFailed: false,
        });
        return;
      }

      if (desiredSrc === this.data.mainSrc) {
        if (!this.data.mainFailed) {
          this.setData({
            ...basePatch,
            desiredSrc,
            prefetchSrc: '',
            prefetchFailed: false,
          });
          return;
        }

        this.setData({
          ...basePatch,
          desiredSrc,
          prefetchSrc: desiredSrc,
          prefetchFailed: false,
        });
        return;
      }

      if (this.data.mainSrc === '' || this.data.mainFailed) {
        this.setData({
          ...basePatch,
          desiredSrc,
          mainSrc: desiredSrc,
          mainFailed: false,
          prefetchSrc: '',
          prefetchFailed: false,
        });
        return;
      }

      if (this.data.prefetchSrc === desiredSrc) {
        this.setData({
          ...basePatch,
          desiredSrc,
        });
        return;
      }

      this.setData({
        ...basePatch,
        desiredSrc,
        prefetchSrc: desiredSrc,
        prefetchFailed: false,
      });
    },

    onMainLoad(event: WechatMiniprogram.CustomEvent<WechatMiniprogram.GeneralCallbackResult>) {
      if (this.data.mainSrc === '') {
        return;
      }
      this.setData({
        mainFailed: false,
      });
      if (this.data.mainSrc === this.data.desiredSrc) {
        this.triggerEvent('load', event.detail);
      }
    },

    onMainError(event: WechatMiniprogram.CustomEvent<WechatMiniprogram.GeneralCallbackResult>) {
      if (this.data.mainSrc === '') {
        return;
      }
      this.setData({
        mainFailed: true,
      });
      if (this.data.mainSrc === this.data.desiredSrc) {
        this.triggerEvent('error', event.detail);
      }
    },

    onPrefetchLoad() {
      if (this.data.prefetchSrc === '') {
        return;
      }

      if (this.data.prefetchSrc !== this.data.desiredSrc) {
        this.setData({
          prefetchFailed: false,
        });
        return;
      }

      this.setData({
        mainSrc: this.data.prefetchSrc,
        mainFailed: false,
        prefetchSrc: '',
        prefetchFailed: false,
      });
    },

    onPrefetchError() {
      if (this.data.prefetchSrc === '') {
        return;
      }
      this.setData({
        prefetchFailed: true,
        prefetchSrc: '',
      });
    },
  },
});
