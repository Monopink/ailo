const AVATAR_PRESET_SIZE = {
  small: '80rpx',
  medium: '96rpx',
  large: '128rpx',
} as const;

type AvatarPresetSize = keyof typeof AVATAR_PRESET_SIZE;
type AvatarBufferIndex = 0 | 1;

type AvatarComponentData = {
  sizeStyle: string;
  desiredSrc: string;
  activeBuffer: AvatarBufferIndex;
  src0: string;
  src1: string;
  loaded0: boolean;
  loaded1: boolean;
  failed0: boolean;
  failed1: boolean;
  placeholderFailed: boolean;
  showPlaceholderIcon: boolean;
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

const isBufferLoading = (data: AvatarComponentData, buffer: AvatarBufferIndex): boolean => {
  const desired = data.desiredSrc;
  if (desired === '') {
    return false;
  }
  if (buffer === 0) {
    return data.src0 === desired && !data.loaded0 && !data.failed0;
  }
  return data.src1 === desired && !data.loaded1 && !data.failed1;
};

const hasActiveLoadedImage = (data: AvatarComponentData): boolean => {
  if (data.activeBuffer === 0) {
    return data.src0 !== '' && data.loaded0;
  }
  return data.src1 !== '' && data.loaded1;
};

const resolvePlaceholderIconVisibility = (
  data: AvatarComponentData,
  placeholderSrc: string
): boolean => {
  if (data.placeholderFailed) {
    return false;
  }
  if (resolveNonEmptyString(placeholderSrc) === '') {
    return false;
  }
  if (hasActiveLoadedImage(data)) {
    return false;
  }
  const isLoading = isBufferLoading(data, 0) || isBufferLoading(data, 1);
  return !isLoading;
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
    placeholderSrc: {
      type: String,
      value: '',
    },
  },

  data: {
    sizeStyle: DEFAULT_SIZE_STYLE,
    desiredSrc: '',
    activeBuffer: 0,
    src0: '',
    src1: '',
    loaded0: false,
    loaded1: false,
    failed0: false,
    failed1: false,
    placeholderFailed: false,
    showPlaceholderIcon: true,
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

      if (desiredSrc === '') {
        const next: Partial<AvatarComponentData> = {
          desiredSrc: '',
          sizeStyle,
          activeBuffer: 0,
          src0: '',
          src1: '',
          loaded0: false,
          loaded1: false,
          failed0: false,
          failed1: false,
        };
        const patched: Partial<AvatarComponentData> = {
          ...next,
          showPlaceholderIcon: resolvePlaceholderIconVisibility(
            { ...this.data, ...next } as AvatarComponentData,
            this.data.placeholderSrc
          ),
        };
        this.setData(patched);
        return;
      }

      const next: Partial<AvatarComponentData> = {
        desiredSrc,
        sizeStyle,
      };

      const active = this.data.activeBuffer;
      const inactive: AvatarBufferIndex = active === 0 ? 1 : 0;
      const activeSrc = active === 0 ? this.data.src0 : this.data.src1;
      const inactiveSrc = inactive === 0 ? this.data.src0 : this.data.src1;
      const activeLoaded = active === 0 ? this.data.loaded0 : this.data.loaded1;

      if (activeSrc === desiredSrc) {
        const nextData = { ...this.data, ...next } as AvatarComponentData;
        this.setData({
          ...next,
          showPlaceholderIcon: resolvePlaceholderIconVisibility(nextData, this.data.placeholderSrc),
        });
        return;
      }

      if (!activeLoaded && activeSrc === '') {
        next.activeBuffer = 0;
        next.src0 = desiredSrc;
        next.loaded0 = false;
        next.failed0 = false;
        next.src1 = '';
        next.loaded1 = false;
        next.failed1 = false;
      } else {
        if (inactiveSrc !== desiredSrc) {
          if (inactive === 0) {
            next.src0 = desiredSrc;
            next.loaded0 = false;
            next.failed0 = false;
          } else {
            next.src1 = desiredSrc;
            next.loaded1 = false;
            next.failed1 = false;
          }
        }
      }

      const nextData = { ...this.data, ...next } as AvatarComponentData;
      next.showPlaceholderIcon = resolvePlaceholderIconVisibility(
        nextData,
        this.data.placeholderSrc
      );
      this.setData(next);
    },

    onBufferLoad(event: WechatMiniprogram.CustomEvent<WechatMiniprogram.GeneralCallbackResult>) {
      const buffer = Number((event.currentTarget.dataset as { buffer?: unknown }).buffer);
      if (buffer !== 0 && buffer !== 1) {
        return;
      }

      const desiredSrc = this.data.desiredSrc;
      if (desiredSrc === '') {
        return;
      }

      const bufferSrc = buffer === 0 ? this.data.src0 : this.data.src1;
      if (bufferSrc === '') {
        return;
      }

      const patch: Partial<AvatarComponentData> = {};
      if (buffer === 0) {
        patch.loaded0 = true;
        patch.failed0 = false;
      } else {
        patch.loaded1 = true;
        patch.failed1 = false;
      }

      if (bufferSrc === desiredSrc) {
        patch.activeBuffer = buffer;
        patch.showPlaceholderIcon = resolvePlaceholderIconVisibility(
          { ...this.data, ...patch } as AvatarComponentData,
          this.data.placeholderSrc
        );
        this.setData(patch);
        this.triggerEvent('load', event.detail);
        return;
      }

      patch.showPlaceholderIcon = resolvePlaceholderIconVisibility(
        { ...this.data, ...patch } as AvatarComponentData,
        this.data.placeholderSrc
      );
      this.setData(patch);
    },

    onPlaceholderError() {
      const patch: Partial<AvatarComponentData> = {
        placeholderFailed: true,
      };
      patch.showPlaceholderIcon = resolvePlaceholderIconVisibility(
        { ...this.data, ...patch } as AvatarComponentData,
        ''
      );
      this.setData(patch);
    },

    onBufferError(event: WechatMiniprogram.CustomEvent<WechatMiniprogram.GeneralCallbackResult>) {
      const buffer = Number((event.currentTarget.dataset as { buffer?: unknown }).buffer);
      if (buffer !== 0 && buffer !== 1) {
        return;
      }

      const desiredSrc = this.data.desiredSrc;
      const bufferSrc = buffer === 0 ? this.data.src0 : this.data.src1;
      if (desiredSrc === '' || bufferSrc === '') {
        return;
      }

      const patch: Partial<AvatarComponentData> = {};
      if (buffer === 0) {
        patch.loaded0 = false;
        patch.failed0 = true;
      } else {
        patch.loaded1 = false;
        patch.failed1 = true;
      }

      patch.showPlaceholderIcon = resolvePlaceholderIconVisibility(
        { ...this.data, ...patch } as AvatarComponentData,
        this.data.placeholderSrc
      );
      this.setData(patch);
      if (bufferSrc === desiredSrc) {
        this.triggerEvent('error', event.detail);
      }
    },
  },
});
