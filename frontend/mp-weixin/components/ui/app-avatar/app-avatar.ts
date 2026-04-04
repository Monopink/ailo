const AVATAR_PRESET_SIZE = {
  small: '80rpx',
  medium: '96rpx',
  large: '128rpx',
} as const;

type AvatarPresetSize = keyof typeof AVATAR_PRESET_SIZE;
type AvatarStatus = 'empty' | 'loading' | 'success' | 'error';

type AvatarComponentData = {
  status: AvatarStatus;
  sizeStyle: string;
  showImage: boolean;
  showPlaceholder: boolean;
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
    hideOnLoadFailed: {
      type: Boolean,
      value: false,
    },
    placeholderSrc: {
      type: String,
      value: '/assets/icons/profile.svg',
    },
  },

  data: {
    status: 'empty',
    sizeStyle: DEFAULT_SIZE_STYLE,
    showImage: false,
    showPlaceholder: true,
  } as AvatarComponentData,

  lifetimes: {
    attached() {
      this.refreshRenderState();
    },
  },

  observers: {
    'src,size'() {
      this.refreshRenderState();
    },
  },

  methods: {
    refreshRenderState() {
      const src = typeof this.data.src === 'string' ? this.data.src.trim() : '';
      const nextStatus: AvatarStatus = src === '' ? 'empty' : 'loading';
      this.setData({
        status: nextStatus,
        sizeStyle: resolveSizeStyle(this.data.size),
        showImage: src !== '',
        showPlaceholder: src === '',
      });
    },

    onImageLoad(event: WechatMiniprogram.CustomEvent<WechatMiniprogram.GeneralCallbackResult>) {
      this.setData({
        status: 'success',
        showImage: true,
        showPlaceholder: false,
      });
      this.triggerEvent('load', event.detail);
    },

    onImageError(event: WechatMiniprogram.CustomEvent<WechatMiniprogram.GeneralCallbackResult>) {
      const shouldHide = this.data.hideOnLoadFailed;
      this.setData({
        status: 'error',
        showImage: !shouldHide,
        showPlaceholder: !shouldHide,
      });
      this.triggerEvent('error', event.detail);
    },

    onPlaceholderError() {
      this.setData({ showPlaceholder: false });
    },
  },
});
