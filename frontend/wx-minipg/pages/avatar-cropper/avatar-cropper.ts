import { getLogger } from '../../utils/logger';
import { isDefined, isNonEmptyString } from '../../utils/guards';

const logger = getLogger('AvatarCropper');
const OUTPUT_SIZE = 512;
const MAX_SCALE = 4;

interface CropperInternalState {
  imageWidth: number;
  imageHeight: number;
  baseScale: number;
}

interface AvatarCropperPageData {
  containerSize: number;
  imagePath: string;
  displayWidth: number;
  displayHeight: number;
  x: number;
  y: number;
  scale: number;
  minScale: number;
  maxScale: number;
  isReady: boolean;
  isSaving: boolean;
}

interface AvatarCropperPageCustom {
  _imageInfo?: CropperInternalState;
  _hasCompleted?: boolean;
  initializeCropper(filePath: string): Promise<void>;
  handleChange(event: WechatMiniprogram.CustomEvent<{ x: number; y: number }>): void;
  handleScale(event: WechatMiniprogram.CustomEvent<{ scale: number; x: number; y: number }>): void;
  handleConfirm(): Promise<void>;
  handleCancel(): void;
  notifyOpener(eventName: string, payload?: Record<string, unknown>): void;
}

Page<AvatarCropperPageData, AvatarCropperPageCustom>({
  data: {
    containerSize: 320,
    imagePath: '',
    displayWidth: 0,
    displayHeight: 0,
    x: 0,
    y: 0,
    scale: 1,
    minScale: 1,
    maxScale: MAX_SCALE,
    isReady: false,
    isSaving: false,
  },

  onLoad() {
    const systemInfo = wx.getSystemInfoSync();
    const containerSize = Math.min(systemInfo.windowWidth - 64, 320);
    this.setData({ containerSize });
    this._hasCompleted = false;

    const eventChannel = this.getOpenerEventChannel();
    eventChannel.on('init', (payload: { filePath?: string }) => {
      if (isNonEmptyString(payload.filePath)) {
        void this.initializeCropper(payload.filePath);
      }
    });
  },

  onUnload() {
    if (!this._hasCompleted) {
      this.notifyOpener('cropCancel');
    }
  },

  async initializeCropper(filePath: string) {
    try {
      const info = await getImageInfo(filePath);
      const minSide = Math.min(info.width, info.height);
      const baseScale = this.data.containerSize / minSide;
      const displayWidth = info.width * baseScale;
      const displayHeight = info.height * baseScale;
      const initialX = (this.data.containerSize - displayWidth) / 2;
      const initialY = (this.data.containerSize - displayHeight) / 2;

      this._imageInfo = {
        imageWidth: info.width,
        imageHeight: info.height,
        baseScale,
      };

      this.setData({
        imagePath: filePath,
        displayWidth,
        displayHeight,
        x: initialX,
        y: initialY,
        scale: 1,
        minScale: 1,
        maxScale: MAX_SCALE,
        isReady: true,
      });
    } catch (error) {
      logger.error('Failed to initialize cropper', {
        error: error instanceof Error ? error.message : String(error),
      });
      void wx.showToast({
        title: '图片加载失败，请重试',
        icon: 'none',
      });
      setTimeout(() => {
        void wx.navigateBack();
      }, 500);
    }
  },

  handleChange(event) {
    const { x, y } = event.detail;
    const clamped = clampPosition(this.data.containerSize, this._imageInfo, x, y, this.data.scale);
    if (clamped.x !== this.data.x || clamped.y !== this.data.y) {
      this.setData(clamped);
    }
  },

  handleScale(event) {
    const { scale, x, y } = event.detail;
    const clamped = clampPosition(this.data.containerSize, this._imageInfo, x, y, scale);
    this.setData({
      scale,
      x: clamped.x,
      y: clamped.y,
    });
  },

  async handleConfirm() {
    if (this.data.isSaving || !isDefined(this._imageInfo)) {
      return;
    }

    this.setData({ isSaving: true });

    try {
      const croppedPath = await cropImageToSquare({
        imagePath: this.data.imagePath,
        imageInfo: this._imageInfo,
        containerSize: this.data.containerSize,
        position: { x: this.data.x, y: this.data.y },
        scale: this.data.scale,
      });

      this._hasCompleted = true;
      this.notifyOpener('cropComplete', { tempFilePath: croppedPath });
      void wx.navigateBack();
    } catch (error) {
      logger.error('Crop failed', {
        error: error instanceof Error ? error.message : String(error),
      });
      void wx.showToast({
        title: '裁剪失败，请重试',
        icon: 'none',
      });
      this.setData({ isSaving: false });
    }
  },

  handleCancel() {
    this._hasCompleted = true;
    this.notifyOpener('cropCancel');
    void wx.navigateBack();
  },

  notifyOpener(eventName, payload = {}) {
    const eventChannel = this.getOpenerEventChannel();
    eventChannel.emit(eventName, payload);
  },
});

function getImageInfo(
  filePath: string
): Promise<WechatMiniprogram.GetImageInfoSuccessCallbackResult> {
  return new Promise((resolve, reject) => {
    wx.getImageInfo({
      src: filePath,
      success: resolve,
      fail: reject,
    });
  });
}

function cropImageToSquare(options: {
  imagePath: string;
  imageInfo: CropperInternalState;
  containerSize: number;
  position: { x: number; y: number };
  scale: number;
}): Promise<string> {
  const { imagePath, imageInfo, containerSize, position, scale } = options;
  const effectiveScale = imageInfo.baseScale * scale;
  const sourceSize = containerSize / effectiveScale;
  let sourceX = -position.x / effectiveScale;
  let sourceY = -position.y / effectiveScale;

  sourceX = Math.max(0, Math.min(imageInfo.imageWidth - sourceSize, sourceX));
  sourceY = Math.max(0, Math.min(imageInfo.imageHeight - sourceSize, sourceY));

  return new Promise((resolve, reject) => {
    const ctx = wx.createCanvasContext('cropCanvas');
    ctx.drawImage(
      imagePath,
      sourceX,
      sourceY,
      sourceSize,
      sourceSize,
      0,
      0,
      OUTPUT_SIZE,
      OUTPUT_SIZE
    );
    ctx.draw(false, () => {
      const options = {
        canvasId: 'cropCanvas',
        width: OUTPUT_SIZE,
        height: OUTPUT_SIZE,
        fileType: 'webp',
        quality: 0.85,
        success: (res: WechatMiniprogram.CanvasToTempFilePathSuccessCallbackResult) =>
          resolve(res.tempFilePath),
        fail: reject,
      } as unknown as WechatMiniprogram.CanvasToTempFilePathOption;
      void wx.canvasToTempFilePath(options, undefined);
    });
  });
}

function clampPosition(
  containerSize: number,
  imageInfo: CropperInternalState | undefined,
  x: number,
  y: number,
  scale: number
): { x: number; y: number } {
  if (!isDefined(imageInfo)) {
    return { x, y };
  }
  const width = imageInfo.imageWidth * imageInfo.baseScale * scale;
  const height = imageInfo.imageHeight * imageInfo.baseScale * scale;
  const minX = Math.min(0, containerSize - width);
  const minY = Math.min(0, containerSize - height);
  return {
    x: Math.max(minX, Math.min(0, x)),
    y: Math.max(minY, Math.min(0, y)),
  };
}
