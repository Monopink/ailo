import { getLogger } from '../../utils/logger';
import { isDefined, isNonEmptyString } from '../../utils/guards';

const logger = getLogger('AvatarCropper');
const OUTPUT_SIZE = 512;
const MIN_INPUT_SHORT_SIDE = 256;
const MAX_SCALE = 4;

interface CropperInternalState {
  imageWidth: number;
  imageHeight: number;
  baseScale: number;
}

interface CropTransform {
  x: number;
  y: number;
  scale: number;
}

interface CropSourceRect {
  sourceX: number;
  sourceY: number;
  sourceSize: number;
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
  _transform?: CropTransform;
  initializeCropper(filePath: string): Promise<void>;
  handleChange(event: WechatMiniprogram.CustomEvent<Partial<CropTransform>>): void;
  handleScale(event: WechatMiniprogram.CustomEvent<Partial<CropTransform>>): void;
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
    const containerSize = Math.min(resolveWindowWidth() - 64, 320);
    this.setData({ containerSize });
    this._hasCompleted = false;
    this._transform = { x: 0, y: 0, scale: 1 };

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
      if (minSide < MIN_INPUT_SHORT_SIDE) {
        logger.info('Reject low resolution image for avatar crop', {
          imageWidth: info.width,
          imageHeight: info.height,
          minRequiredShortSide: MIN_INPUT_SHORT_SIDE,
        });
        void wx.showToast({
          title: `图片过小，短边需至少 ${MIN_INPUT_SHORT_SIDE}px`,
          icon: 'none',
        });
        setTimeout(() => {
          void wx.navigateBack();
        }, 600);
        return;
      }

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
      this._transform = {
        x: initialX,
        y: initialY,
        scale: 1,
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
    const nextTransform = resolveNextTransform({
      current: this._transform ?? {
        x: this.data.x,
        y: this.data.y,
        scale: this.data.scale,
      },
      detail: event.detail,
      minScale: this.data.minScale,
      maxScale: this.data.maxScale,
    });
    const clamped = clampPosition(
      this.data.containerSize,
      this._imageInfo,
      nextTransform.x,
      nextTransform.y,
      nextTransform.scale
    );
    const resolved = { ...nextTransform, ...clamped };
    this._transform = resolved;
    if (
      resolved.x !== this.data.x ||
      resolved.y !== this.data.y ||
      resolved.scale !== this.data.scale
    ) {
      this.setData(resolved);
    }
  },

  handleScale(event) {
    const nextTransform = resolveNextTransform({
      current: this._transform ?? {
        x: this.data.x,
        y: this.data.y,
        scale: this.data.scale,
      },
      detail: event.detail,
      minScale: this.data.minScale,
      maxScale: this.data.maxScale,
    });
    const clamped = clampPosition(
      this.data.containerSize,
      this._imageInfo,
      nextTransform.x,
      nextTransform.y,
      nextTransform.scale
    );
    const resolved = { ...nextTransform, ...clamped };
    this._transform = resolved;
    this.setData({
      scale: resolved.scale,
      x: resolved.x,
      y: resolved.y,
    });
  },

  async handleConfirm() {
    if (this.data.isSaving || !isDefined(this._imageInfo)) {
      return;
    }

    this.setData({ isSaving: true });

    try {
      const transform = this._transform ?? {
        x: this.data.x,
        y: this.data.y,
        scale: this.data.scale,
      };
      const croppedPath = await cropImageToSquare({
        imagePath: this.data.imagePath,
        imageInfo: this._imageInfo,
        containerSize: this.data.containerSize,
        position: { x: transform.x, y: transform.y },
        scale: transform.scale,
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
  const cropSourceRect = resolveCropSourceRect(options);
  return drawCroppedAvatarToCanvas(options.imagePath, cropSourceRect);
}

function resolveCropSourceRect(options: {
  imageInfo: CropperInternalState;
  containerSize: number;
  position: { x: number; y: number };
  scale: number;
}): CropSourceRect {
  const { imageInfo, containerSize, position, scale } = options;
  const resolvedScale = Number.isFinite(scale) && scale > 0 ? scale : 1;
  const resolvedX = Number.isFinite(position.x) ? position.x : 0;
  const resolvedY = Number.isFinite(position.y) ? position.y : 0;
  const effectiveScale = imageInfo.baseScale * resolvedScale;
  const sourceSize = containerSize / effectiveScale;
  let sourceX = -resolvedX / effectiveScale;
  let sourceY = -resolvedY / effectiveScale;

  sourceX = Math.max(0, Math.min(imageInfo.imageWidth - sourceSize, sourceX));
  sourceY = Math.max(0, Math.min(imageInfo.imageHeight - sourceSize, sourceY));
  return {
    sourceX,
    sourceY,
    sourceSize,
  };
}

function resolveWindowWidth(): number {
  if (typeof wx.getWindowInfo === 'function') {
    const windowInfo = wx.getWindowInfo();
    if (typeof windowInfo.windowWidth === 'number' && Number.isFinite(windowInfo.windowWidth)) {
      return windowInfo.windowWidth;
    }
  }
  return 375;
}

function resolvePixelRatio(): number {
  if (typeof wx.getWindowInfo === 'function') {
    const windowInfo = wx.getWindowInfo();
    if (typeof windowInfo.pixelRatio === 'number' && Number.isFinite(windowInfo.pixelRatio)) {
      return Math.max(1, windowInfo.pixelRatio);
    }
  }
  return 2;
}

function getCropCanvasNode(): Promise<WechatMiniprogram.Canvas> {
  return new Promise((resolve, reject) => {
    const query = wx.createSelectorQuery();
    query
      .select('#cropCanvas2d')
      .fields({ node: true, size: true }, (result) => {
        const canvas = (result as { node?: WechatMiniprogram.Canvas } | null)?.node;
        if (isDefined(canvas)) {
          resolve(canvas);
          return;
        }
        reject(new Error('CANVAS_NODE_NOT_FOUND'));
      })
      .exec();
  });
}

function loadCanvasImage(
  canvas: WechatMiniprogram.Canvas,
  imagePath: string
): Promise<WechatMiniprogram.Image> {
  return new Promise((resolve, reject) => {
    const image = canvas.createImage();
    image.onload = () => resolve(image);
    image.onerror = (error: unknown) =>
      reject(error instanceof Error ? error : new Error(String(error)));
    image.src = imagePath;
  });
}

function exportCanvasToTempFile2D(canvas: WechatMiniprogram.Canvas): Promise<string> {
  return new Promise((resolve, reject) => {
    const exportOptions = {
      canvas: canvas as unknown as WechatMiniprogram.IAnyObject,
      width: canvas.width,
      height: canvas.height,
      destWidth: OUTPUT_SIZE,
      destHeight: OUTPUT_SIZE,
      fileType: 'webp',
      quality: 0.85,
      success: (res: WechatMiniprogram.CanvasToTempFilePathSuccessCallbackResult) =>
        resolve(res.tempFilePath),
      fail: reject,
    } as unknown as WechatMiniprogram.CanvasToTempFilePathOption;
    void wx.canvasToTempFilePath(exportOptions);
  });
}

function drawCroppedAvatarToCanvasLegacy(
  cropSourceRect: CropSourceRect,
  imagePath: string
): Promise<string> {
  return new Promise((resolve, reject) => {
    const ctx = wx.createCanvasContext('cropCanvasLegacy');
    ctx.drawImage(
      imagePath,
      cropSourceRect.sourceX,
      cropSourceRect.sourceY,
      cropSourceRect.sourceSize,
      cropSourceRect.sourceSize,
      0,
      0,
      OUTPUT_SIZE,
      OUTPUT_SIZE
    );
    ctx.draw(false, () => {
      const exportOptions = {
        canvasId: 'cropCanvasLegacy',
        width: OUTPUT_SIZE,
        height: OUTPUT_SIZE,
        destWidth: OUTPUT_SIZE,
        destHeight: OUTPUT_SIZE,
        fileType: 'webp',
        quality: 0.85,
        success: (res: WechatMiniprogram.CanvasToTempFilePathSuccessCallbackResult) =>
          resolve(res.tempFilePath),
        fail: reject,
      } as unknown as WechatMiniprogram.CanvasToTempFilePathOption;
      void wx.canvasToTempFilePath(exportOptions, undefined);
    });
  });
}

function serializeError(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
}

async function drawCroppedAvatarToCanvas(
  imagePath: string,
  cropSourceRect: CropSourceRect
): Promise<string> {
  try {
    const canvas = await getCropCanvasNode();
    const context = canvas.getContext('2d');
    const dpr = resolvePixelRatio();

    canvas.width = OUTPUT_SIZE * dpr;
    canvas.height = OUTPUT_SIZE * dpr;

    if (typeof context.setTransform === 'function') {
      context.setTransform(dpr, 0, 0, dpr, 0, 0);
    } else {
      context.scale(dpr, dpr);
    }
    context.clearRect(0, 0, OUTPUT_SIZE, OUTPUT_SIZE);

    const image = await loadCanvasImage(canvas, imagePath);
    context.drawImage(
      image,
      cropSourceRect.sourceX,
      cropSourceRect.sourceY,
      cropSourceRect.sourceSize,
      cropSourceRect.sourceSize,
      0,
      0,
      OUTPUT_SIZE,
      OUTPUT_SIZE
    );

    return await exportCanvasToTempFile2D(canvas);
  } catch (error) {
    logger.warn('Canvas 2D crop failed, fallback to legacy canvas', {
      error: serializeError(error),
    });
    return await drawCroppedAvatarToCanvasLegacy(cropSourceRect, imagePath);
  }
}

function resolveNextTransform(params: {
  current: CropTransform;
  detail: Partial<CropTransform> | undefined;
  minScale: number;
  maxScale: number;
}): CropTransform {
  const { current, detail, minScale, maxScale } = params;
  const scaleCandidate =
    typeof detail?.scale === 'number' && Number.isFinite(detail.scale)
      ? detail.scale
      : current.scale;
  const normalizedScale = Math.max(minScale, Math.min(maxScale, scaleCandidate));
  const x = typeof detail?.x === 'number' && Number.isFinite(detail.x) ? detail.x : current.x;
  const y = typeof detail?.y === 'number' && Number.isFinite(detail.y) ? detail.y : current.y;
  return { x, y, scale: normalizedScale };
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
